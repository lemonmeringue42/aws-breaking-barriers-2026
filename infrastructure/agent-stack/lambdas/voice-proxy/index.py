import json
import os
import base64
import asyncio
import boto3
import hashlib
import hmac
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Nova Sonic config
REGION = os.environ.get('AWS_REGION', 'us-east-1')
MODEL_ID = 'amazon.nova-sonic-v1:0'
BEDROCK_ENDPOINT = f'https://bedrock-runtime.{REGION}.amazonaws.com'

# Connection store (use DynamoDB for production)
connections = {}

bedrock = boto3.client('bedrock-runtime', region_name=REGION)


def lambda_handler(event, context):
    """Handle WebSocket events for Nova Sonic voice streaming."""
    route = event.get('requestContext', {}).get('routeKey')
    connection_id = event.get('requestContext', {}).get('connectionId')
    domain = event.get('requestContext', {}).get('domainName')
    stage = event.get('requestContext', {}).get('stage')
    
    if route == '$connect':
        return handle_connect(event, connection_id)
    elif route == '$disconnect':
        return handle_disconnect(connection_id)
    elif route == '$default':
        return handle_message(event, connection_id, domain, stage)
    
    return {'statusCode': 400}


def handle_connect(event, connection_id):
    """Validate token and establish connection."""
    # Extract token from query string
    qs = event.get('queryStringParameters') or {}
    token = qs.get('token')
    
    if not token:
        return {'statusCode': 401, 'body': 'Missing token'}
    
    # In production, validate JWT token against Cognito
    # For now, accept any token
    connections[connection_id] = {
        'state': 'connected',
        'session_id': None,
        'prompt_name': None
    }
    
    return {'statusCode': 200}


def handle_disconnect(connection_id):
    """Clean up connection."""
    connections.pop(connection_id, None)
    return {'statusCode': 200}


def handle_message(event, connection_id, domain, stage):
    """Process incoming WebSocket messages and proxy to Nova Sonic."""
    try:
        body = json.loads(event.get('body', '{}'))
        event_type = body.get('event', {})
        
        # API Gateway management client for sending responses
        apigw = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=f'https://{domain}/{stage}'
        )
        
        # Handle session start - initiate Bedrock stream
        if 'sessionStart' in event_type:
            return start_nova_session(connection_id, body, apigw)
        
        # Handle audio input - forward to Bedrock
        if 'audioInput' in event_type:
            return forward_audio(connection_id, body, apigw)
        
        # Handle session end
        if 'sessionEnd' in event_type:
            return end_session(connection_id)
        
        # Forward other events directly
        return forward_event(connection_id, body, apigw)
        
    except Exception as e:
        print(f'Error: {e}')
        return {'statusCode': 500, 'body': str(e)}


def start_nova_session(connection_id, body, apigw):
    """Initialize Nova Sonic bidirectional stream."""
    try:
        # Store session info
        conn = connections.get(connection_id, {})
        conn['state'] = 'streaming'
        connections[connection_id] = conn
        
        # For bidirectional streaming, we need to use invoke_model_with_response_stream
        # and handle the async nature. In Lambda, we'll batch process.
        
        # Send acknowledgment
        send_to_client(apigw, connection_id, {
            'event': {'sessionStarted': {'status': 'ok'}}
        })
        
        return {'statusCode': 200}
        
    except Exception as e:
        print(f'Session start error: {e}')
        return {'statusCode': 500}


def forward_audio(connection_id, body, apigw):
    """Forward audio chunk to Nova Sonic and stream response."""
    try:
        audio_event = body.get('event', {}).get('audioInput', {})
        audio_content = audio_event.get('content', '')
        prompt_name = audio_event.get('promptName', '')
        
        # Decode audio
        audio_bytes = base64.b64decode(audio_content)
        
        # For real bidirectional streaming, you'd maintain a persistent connection
        # Here we'll use a simplified request-response pattern
        
        # Build Nova Sonic request
        request_body = {
            'inputAudio': {
                'audioConfig': {
                    'sampleRateHertz': 16000,
                    'encoding': 'LINEAR16'
                },
                'audioContent': audio_content
            },
            'outputAudioConfig': {
                'sampleRateHertz': 24000,
                'encoding': 'LINEAR16',
                'voiceId': 'matthew'
            }
        }
        
        # Invoke Nova Sonic with streaming
        response = bedrock.invoke_model_with_response_stream(
            modelId=MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(request_body)
        )
        
        # Stream response chunks back to client
        for event in response.get('body', []):
            chunk = event.get('chunk', {})
            if chunk:
                chunk_data = json.loads(chunk.get('bytes', b'{}').decode())
                
                # Forward text output
                if 'textOutput' in chunk_data:
                    send_to_client(apigw, connection_id, {
                        'event': {'textOutput': chunk_data['textOutput']},
                        'role': chunk_data.get('role', 'ASSISTANT')
                    })
                
                # Forward audio output
                if 'audioOutput' in chunk_data:
                    send_to_client(apigw, connection_id, {
                        'event': {'audioOutput': chunk_data['audioOutput']}
                    })
        
        return {'statusCode': 200}
        
    except Exception as e:
        print(f'Audio forward error: {e}')
        send_to_client(apigw, connection_id, {
            'event': {'error': {'message': str(e)}}
        })
        return {'statusCode': 500}


def forward_event(connection_id, body, apigw):
    """Forward generic events to Nova Sonic."""
    # For events like promptStart, contentStart, etc.
    # These configure the session but don't need immediate response
    return {'statusCode': 200}


def end_session(connection_id):
    """Clean up Nova Sonic session."""
    conn = connections.get(connection_id, {})
    conn['state'] = 'ended'
    connections[connection_id] = conn
    return {'statusCode': 200}


def send_to_client(apigw, connection_id, data):
    """Send message to WebSocket client."""
    try:
        apigw.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode()
        )
    except Exception as e:
        print(f'Send error: {e}')
