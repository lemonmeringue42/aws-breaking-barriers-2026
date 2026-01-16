#!/usr/bin/env python3
"""
Test script to invoke the Citizens Advice agent directly
"""
import boto3
import json
import sys

# Configuration
RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-west-2:732033934792:runtime/agent_agentstack_citizensadv2-JemTSn9BzE"
REGION = "us-west-2"
USER_POOL_ID = "us-west-2_OSUEpnHmo"
CLIENT_ID = "1vctuearov1eotv5soq7r3uvp0"

def get_cognito_token(username, password):
    """Get JWT token from Cognito"""
    client = boto3.client('cognito-idp', region_name=REGION)
    
    try:
        response = client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        return response['AuthenticationResult']['IdToken']
    except Exception as e:
        print(f"❌ Failed to authenticate: {e}")
        return None

def test_agent(token, query):
    """Test the agent with a query"""
    client = boto3.client('bedrock-agentcore-runtime', region_name=REGION)
    
    try:
        print(f"\n🤖 Testing agent with query: {query}")
        print(f"Runtime ARN: {RUNTIME_ARN}\n")
        
        response = client.invoke_runtime(
            runtimeArn=RUNTIME_ARN,
            qualifier='DEFAULT',
            body=json.dumps({
                'prompt': query,
                'user_id': 'test-user',
                'session_id': 'test-session'
            }),
            contentType='application/json',
            accept='application/json'
        )
        
        # Read streaming response
        print("✅ Agent response:")
        print("-" * 50)
        
        for event in response['body']:
            chunk = json.loads(event['chunk']['bytes'].decode('utf-8'))
            if 'data' in chunk:
                print(chunk['data'], end='', flush=True)
        
        print("\n" + "-" * 50)
        return True
        
    except Exception as e:
        print(f"❌ Error invoking agent: {e}")
        return False

def test_without_auth():
    """Test agent endpoint without authentication (will fail but shows connectivity)"""
    import requests
    
    url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{RUNTIME_ARN.replace(':', '%3A').replace('/', '%2F')}/invocations?qualifier=DEFAULT"
    
    print(f"\n🔍 Testing connectivity to: {url}\n")
    
    try:
        response = requests.post(
            url,
            json={'prompt': 'test', 'user_id': 'test', 'session_id': 'test'},
            timeout=5
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        if response.status_code == 401:
            print("\n✅ Agent endpoint is reachable (401 = needs authentication)")
            return True
        elif response.status_code == 403:
            print("\n⚠️  Agent endpoint is reachable but access denied")
            return True
        else:
            print(f"\n❓ Unexpected status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Cannot reach agent: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Citizens Advice Agent Test")
    print("=" * 50)
    
    # Test 1: Connectivity
    print("\n[Test 1] Testing agent endpoint connectivity...")
    test_without_auth()
    
    # Test 2: With authentication (if credentials provided)
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
        query = sys.argv[3] if len(sys.argv) > 3 else "I need help with Universal Credit"
        
        print("\n[Test 2] Testing with authentication...")
        token = get_cognito_token(username, password)
        
        if token:
            print("✅ Got authentication token")
            test_agent(token, query)
        else:
            print("❌ Could not get authentication token")
    else:
        print("\n[Test 2] Skipped (no credentials provided)")
        print("\nTo test with authentication:")
        print(f"  python3 {sys.argv[0]} <username> <password> [query]")
    
    print("\n" + "=" * 50)
