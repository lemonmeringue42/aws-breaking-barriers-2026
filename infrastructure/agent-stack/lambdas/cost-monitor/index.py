import json
import boto3
from datetime import datetime, timedelta
from decimal import Decimal

cloudwatch = boto3.client('cloudwatch')
pricing = boto3.client('pricing', region_name='us-east-1')  # Pricing API only in us-east-1

# Cache pricing data (refreshed once per day)
PRICING_CACHE = {}
CACHE_TIMESTAMP = None


def lambda_handler(event, context):
    """
    Fetch Bedrock usage metrics and calculate costs using AWS Pricing API.
    """
    try:
        # Get time range
        end_time = datetime.utcnow()
        start_time_today = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time_month = end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get pricing from AWS Pricing API
        model_pricing = get_bedrock_pricing()
        
        # Get today's metrics
        today_stats = get_bedrock_metrics(start_time_today, end_time)
        
        # Get this month's metrics
        month_stats = get_bedrock_metrics(start_time_month, end_time)
        
        # Calculate costs
        today_cost = calculate_cost(today_stats, model_pricing)
        month_cost = calculate_cost(month_stats, model_pricing)
        
        # Calculate averages
        today_conversations = today_stats.get('invocations', 0)
        avg_cost_per_conversation = float(today_cost / today_conversations) if today_conversations > 0 else 0
        
        response = {
            'today': {
                'cost': float(today_cost),
                'conversations': today_conversations,
                'input_tokens': today_stats.get('input_tokens', 0),
                'output_tokens': today_stats.get('output_tokens', 0),
                'avg_cost_per_conversation': round(avg_cost_per_conversation, 4)
            },
            'month': {
                'cost': float(month_cost),
                'conversations': month_stats.get('invocations', 0),
                'input_tokens': month_stats.get('input_tokens', 0),
                'output_tokens': month_stats.get('output_tokens', 0)
            },
            'pricing': {
                'input_per_1k': float(model_pricing['input_tokens']),
                'output_per_1k': float(model_pricing['output_tokens']),
                'model': model_pricing['model_name']
            },
            'timestamp': end_time.isoformat()
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps(response)
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def get_bedrock_pricing():
    """
    Fetch Bedrock pricing from AWS Pricing API with caching.
    """
    global PRICING_CACHE, CACHE_TIMESTAMP
    
    # Check cache (refresh once per day)
    if CACHE_TIMESTAMP and (datetime.utcnow() - CACHE_TIMESTAMP).days < 1 and PRICING_CACHE:
        print("Using cached pricing")
        return PRICING_CACHE
    
    try:
        print("Fetching pricing from AWS Pricing API...")
        
        # Query pricing for Claude Sonnet 4.5
        response = pricing.get_products(
            ServiceCode='AmazonBedrock',
            Filters=[
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'modelId',
                    'Value': 'anthropic.claude-sonnet-4-5-v1'
                },
                {
                    'Type': 'TERM_MATCH',
                    'Field': 'usagetype',
                    'Value': 'ModelInference'
                }
            ],
            MaxResults=10
        )
        
        # Parse pricing data
        input_price = Decimal('0.003')  # Default fallback
        output_price = Decimal('0.015')  # Default fallback
        
        for price_item in response.get('PriceList', []):
            price_data = json.loads(price_item)
            
            # Extract pricing from the complex AWS Pricing API structure
            terms = price_data.get('terms', {}).get('OnDemand', {})
            for term_key, term_value in terms.items():
                price_dimensions = term_value.get('priceDimensions', {})
                for dim_key, dim_value in price_dimensions.items():
                    unit = dim_value.get('unit', '')
                    price_per_unit = Decimal(dim_value.get('pricePerUnit', {}).get('USD', '0'))
                    
                    # Identify input vs output tokens
                    description = dim_value.get('description', '').lower()
                    if 'input' in description:
                        input_price = price_per_unit
                    elif 'output' in description:
                        output_price = price_per_unit
        
        pricing_data = {
            'input_tokens': input_price,
            'output_tokens': output_price,
            'model_name': 'Claude Sonnet 4.5'
        }
        
        # Update cache
        PRICING_CACHE = pricing_data
        CACHE_TIMESTAMP = datetime.utcnow()
        
        print(f"Pricing fetched: Input=${input_price}/1K, Output=${output_price}/1K")
        return pricing_data
        
    except Exception as e:
        print(f"Error fetching pricing, using defaults: {e}")
        # Fallback to hardcoded pricing
        return {
            'input_tokens': Decimal('0.003'),
            'output_tokens': Decimal('0.015'),
            'model_name': 'Claude Sonnet 4.5 (estimated)'
        }


def get_bedrock_metrics(start_time, end_time):
    """
    Fetch Bedrock metrics from CloudWatch.
    """
    try:
        # Get invocation count
        invocations_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Bedrock',
            MetricName='Invocations',
            Dimensions=[
                {'Name': 'ModelId', 'Value': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,  # 1 hour
            Statistics=['Sum']
        )
        
        invocations = sum(point['Sum'] for point in invocations_response['Datapoints'])
        
        # Get input tokens
        input_tokens_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Bedrock',
            MetricName='InputTokens',
            Dimensions=[
                {'Name': 'ModelId', 'Value': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Sum']
        )
        
        input_tokens = sum(point['Sum'] for point in input_tokens_response['Datapoints'])
        
        # Get output tokens
        output_tokens_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Bedrock',
            MetricName='OutputTokens',
            Dimensions=[
                {'Name': 'ModelId', 'Value': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Sum']
        )
        
        output_tokens = sum(point['Sum'] for point in output_tokens_response['Datapoints'])
        
        return {
            'invocations': int(invocations),
            'input_tokens': int(input_tokens),
            'output_tokens': int(output_tokens)
        }
        
    except Exception as e:
        print(f"Error fetching metrics: {e}")
        return {
            'invocations': 0,
            'input_tokens': 0,
            'output_tokens': 0
        }


def calculate_cost(stats, pricing):
    """
    Calculate cost based on token usage and AWS pricing.
    """
    # Pricing is per 1K tokens, convert to per token
    input_cost = Decimal(stats['input_tokens']) * pricing['input_tokens'] / 1000
    output_cost = Decimal(stats['output_tokens']) * pricing['output_tokens'] / 1000
    total_cost = input_cost + output_cost
    return round(total_cost, 4)

