import * as cdk from 'aws-cdk-lib';
import * as agentcore from '@aws-cdk/aws-bedrock-agentcore-alpha';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as customResources from 'aws-cdk-lib/custom-resources';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';
import { GatewayConstruct } from './constructs/gateway-construct';
import * as path from 'path';
import * as fs from 'fs';

const sanitizeName = (name: string) =>
  name.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_');

const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

export class AgentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    cdk.Tags.of(this).add('DeploymentId', DEPLOYMENT_ID);

    // Import Cognito from Amplify - HARDCODED to fix JWT mismatch
    const userPoolId = 'us-west-2_OSUEpnHmo';
    const clientId = '1vctuearov1eotv5soq7r3uvp0';
    const cognitoRegion = 'us-west-2';
    const discoveryUrl = `https://cognito-idp.${cognitoRegion}.amazonaws.com/${userPoolId}/.well-known/openid-configuration`;
    const machineClientId = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Auth-MachineClientId`);

    const userPool = cognito.UserPool.fromUserPoolId(this, 'ImportedUserPool', userPoolId);

    // Import DynamoDB tables
    const userProfileTableName = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-UserProfileTableName`);
    const notesTableName = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-NotesTableName`);
    const feedbackTableName = cdk.Fn.importValue(`ConciergeAgent-${DEPLOYMENT_ID}-Data-FeedbackTableName`);

    // Import MCP runtime ARN
    const notesRuntimeArn = cdk.Fn.importValue(`NotesStack-${DEPLOYMENT_ID}-RuntimeArn`);

    // OAuth Provider Lambda
    const oauthProviderRole = new iam.Role(this, 'OAuthProviderLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        OAuthProviderPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'bedrock-agentcore:CreateOAuth2CredentialProvider',
                'bedrock-agentcore:DeleteOAuth2CredentialProvider',
                'bedrock-agentcore:ListOAuth2CredentialProviders',
                'bedrock-agentcore:GetOAuth2CredentialProvider',
                'bedrock-agentcore:CreateTokenVault',
                'bedrock-agentcore:DeleteTokenVault',
                'bedrock-agentcore:GetTokenVault',
                'secretsmanager:CreateSecret',
                'secretsmanager:DeleteSecret',
                'secretsmanager:GetSecretValue',
                'secretsmanager:PutSecretValue',
                'cognito-idp:DescribeUserPoolClient'
              ],
              resources: ['*']
            })
          ]
        })
      }
    });

    const oauthProviderLambda = new lambda.Function(this, 'OAuthProviderLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambdas', 'oauth-provider')),
      timeout: cdk.Duration.minutes(5),
      role: oauthProviderRole,
    });

    const oauthProvider = new customResources.Provider(this, 'OAuthProvider', {
      onEventHandler: oauthProviderLambda
    });

    const oauthCredentialProvider = new cdk.CustomResource(this, 'OAuthCredentialProvider', {
      serviceToken: oauthProvider.serviceToken,
      properties: {
        ProviderName: sanitizeName(`oauth_provider_${this.stackName}`),
        UserPoolId: userPoolId,
        ClientId: machineClientId,
        DiscoveryUrl: discoveryUrl,
        Version: '2'
      }
    });

    const oauthProviderArn = oauthCredentialProvider.getAttString('ProviderArn');

    // Memory with Long-Term Memory Strategies
    const memory = new agentcore.Memory(this, 'Memory', {
      memoryName: sanitizeName(`memory_${this.stackName}`),
      description: 'Memory for Citizens Advice Agent with long-term memory strategies',
      memoryStrategies: [
        // Semantic memory - extracts facts and knowledge from conversations
        agentcore.MemoryStrategy.usingSemantic({
          name: 'semantic_facts',
          description: 'Extracts factual information about user situations, case details, and advice given',
          namespaces: ['/users/{actorId}/facts'],
        }),
        // User preferences - captures user preferences and patterns
        agentcore.MemoryStrategy.usingUserPreference({
          name: 'user_preferences',
          description: 'Captures user preferences like communication style, accessibility needs, and topic interests',
          namespaces: ['/users/{actorId}/preferences'],
        }),
        // Summarization - creates concise summaries of conversations
        agentcore.MemoryStrategy.usingSummarization({
          name: 'conversation_summaries',
          description: 'Summarizes key points from advice sessions for quick context recall',
          namespaces: ['/users/{actorId}/sessions/{sessionId}/summaries'],
        }),
      ],
    });

    // Case Queue Table for triage
    const caseQueueTable = new dynamodb.Table(this, 'CaseQueueTable', {
      tableName: `CaseQueue-${DEPLOYMENT_ID}`,
      partitionKey: { name: 'caseId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: true,
    });

    // GSI for querying by urgency level
    caseQueueTable.addGlobalSecondaryIndex({
      indexName: 'UrgencyIndex',
      partitionKey: { name: 'urgencyLevel', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
    });

    // GSI for querying by user
    caseQueueTable.addGlobalSecondaryIndex({
      indexName: 'UserIndex',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
    });

    // Bookings Table for appointment scheduling
    const bookingsTable = new dynamodb.Table(this, 'BookingsTable', {
      tableName: `Bookings-${DEPLOYMENT_ID}`,
      partitionKey: { name: 'bookingId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    bookingsTable.addGlobalSecondaryIndex({
      indexName: 'SlotIndex',
      partitionKey: { name: 'slotId', type: dynamodb.AttributeType.STRING },
    });

    bookingsTable.addGlobalSecondaryIndex({
      indexName: 'UserBookingsIndex',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'appointmentTime', type: dynamodb.AttributeType.STRING },
    });

    // SNS Topic for crisis alerts
    const crisisAlertTopic = new sns.Topic(this, 'CrisisAlertTopic', {
      topicName: `CrisisAlerts-${DEPLOYMENT_ID}`,
      displayName: 'Citizens Advice Crisis Case Alerts',
    });

    // Subscribe emails to crisis alerts
    crisisAlertTopic.addSubscription(
      new subscriptions.EmailSubscription('erica.martin@tpicap.com')
    );
    crisisAlertTopic.addSubscription(
      new subscriptions.EmailSubscription('ericamartin421@gmail.com')
    );

    // S3 Bucket for generated documents
    const documentsBucket = new s3.Bucket(this, 'DocumentsBucket', {
      bucketName: `citizens-advice-documents-${DEPLOYMENT_ID}-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [{
        expiration: cdk.Duration.days(30), // Auto-delete documents after 30 days
      }],
      cors: [{
        allowedMethods: [s3.HttpMethods.GET],
        allowedOrigins: ['*'],
        allowedHeaders: ['*'],
      }],
    });

    // Agent execution role
    const agentRole = new iam.Role(this, 'AgentRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
    });

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['dynamodb:GetItem', 'dynamodb:Scan', 'dynamodb:UpdateItem', 'dynamodb:Query', 'dynamodb:PutItem', 'dynamodb:DeleteItem', 'dynamodb:BatchWriteItem'],
      resources: [
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${userProfileTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${userProfileTableName}/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${notesTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${notesTableName}/index/*`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${feedbackTableName}`,
        `arn:aws:dynamodb:${this.region}:${this.account}:table/${feedbackTableName}/index/*`,
        caseQueueTable.tableArn,
        `${caseQueueTable.tableArn}/index/*`,
        bookingsTable.tableArn,
        `${bookingsTable.tableArn}/index/*`
      ]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
      resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['sns:Publish'],
      resources: [crisisAlertTopic.topicArn]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['s3:PutObject', 's3:GetObject', 's3:DeleteObject'],
      resources: [`${documentsBucket.bucketArn}/*`]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'bedrock-agentcore:GetMemory',
        'bedrock-agentcore:ListMemories',
        'bedrock-agentcore:CreateEvent',
        'bedrock-agentcore:GetEvent',
        'bedrock-agentcore:ListEvents',
        'bedrock-agentcore:RetrieveMemoryRecords',
        'bedrock-agentcore:ListMemoryRecords',
        'bedrock-agentcore:BatchCreateMemoryRecords',
        'bedrock-agentcore:GetMemoryRecord',
        'bedrock-agentcore:StartMemoryExtractionJob',
        'bedrock-agentcore:ListMemoryExtractionJobs',
        'bedrock-agentcore:ListActors',
        'bedrock-agentcore:ListSessions'
      ],
      resources: [memory.memoryArn]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: [
        `arn:aws:bedrock:*::foundation-model/*`,
        `arn:aws:bedrock:*:${this.account}:inference-profile/*`
      ]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:InvokeGateway'],
      resources: ['*']
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ecr:GetAuthorizationToken', 'ecr:BatchCheckLayerAvailability', 'ecr:GetDownloadUrlForLayer', 'ecr:BatchGetImage'],
      resources: ['*']
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['cognito-idp:DescribeUserPoolClient', 'cognito-idp:DescribeUserPool'],
      resources: [`arn:aws:cognito-idp:${this.region}:${this.account}:userpool/${userPoolId}`]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock:Retrieve'],
      resources: [
        `arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/*`
      ]
    }));

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter'],
      resources: [`arn:aws:ssm:${this.region}:${this.account}:parameter/citizens-advice-agent/${DEPLOYMENT_ID}/*`]
    }));

    // Agent runtime
    const runtime = new agentcore.Runtime(this, 'Runtime', {
      runtimeName: sanitizeName(`agent_${this.stackName}`),
      agentRuntimeArtifact: agentcore.AgentRuntimeArtifact.fromAsset(
        path.join(__dirname, '../../..', 'concierge_agent', 'supervisor_agent')
      ),
      executionRole: agentRole,
      protocolConfiguration: agentcore.ProtocolType.HTTP,
      networkConfiguration: agentcore.RuntimeNetworkConfiguration.usingPublicNetwork(),
      authorizerConfiguration: agentcore.RuntimeAuthorizerConfiguration.usingJWT(
        discoveryUrl,
        [clientId, machineClientId]
      ),
      environmentVariables: {
        MEMORY_ID: memory.memoryId,
        USER_PROFILE_TABLE_NAME: userProfileTableName,
        NOTES_TABLE_NAME: notesTableName,
        FEEDBACK_TABLE_NAME: feedbackTableName,
        CASE_QUEUE_TABLE_NAME: caseQueueTable.tableName,
        BOOKINGS_TABLE_NAME: bookingsTable.tableName,
        CRISIS_ALERT_TOPIC_ARN: crisisAlertTopic.topicArn,
        DOCUMENTS_BUCKET_NAME: documentsBucket.bucketName,
        DEPLOYMENT_ID: DEPLOYMENT_ID,
        GATEWAY_CLIENT_ID: machineClientId,
        GATEWAY_USER_POOL_ID: userPoolId,
        GATEWAY_SCOPE: 'citizens-advice-gateway/invoke',
        LOCAL_KB_ID: process.env.LOCAL_KB_ID || '',
        NATIONAL_KB_ID: process.env.NATIONAL_KB_ID || '',
      },
      description: 'Citizens Advice Agent Runtime'
    });

    // Gateway
    const gateway = new GatewayConstruct(this, 'Gateway', {
      gatewayName: sanitizeName(`gateway_${this.stackName}`).replace(/_/g, '-'),
      mcpRuntimeArns: [
        { name: 'NotesTools', arn: notesRuntimeArn }
      ],
      cognitoClientId: machineClientId,
      cognitoDiscoveryUrl: discoveryUrl,
      oauthProviderArn: oauthProviderArn,
      oauthScope: 'citizens-advice-gateway/invoke'
    });

    const gatewayUrlParameter = new cdk.aws_ssm.StringParameter(this, 'GatewayUrlParameter', {
      parameterName: `/citizens-advice-agent/${DEPLOYMENT_ID}/gateway-url`,
      stringValue: gateway.gatewayUrl,
      tier: cdk.aws_ssm.ParameterTier.STANDARD,
    });

    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter'],
      resources: [gatewayUrlParameter.parameterArn]
    }));

    // Cost Monitor Lambda
    const costMonitorRole = new iam.Role(this, 'CostMonitorRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
    });

    costMonitorRole.addToPolicy(new iam.PolicyStatement({
      actions: ['cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics'],
      resources: ['*']
    }));

    costMonitorRole.addToPolicy(new iam.PolicyStatement({
      actions: ['pricing:GetProducts'],
      resources: ['*']
    }));

    const costMonitorLambda = new lambda.Function(this, 'CostMonitorLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambdas', 'cost-monitor')),
      timeout: cdk.Duration.seconds(30),
      role: costMonitorRole,
    });

    // API Gateway for cost monitoring
    const costApi = new apigateway.RestApi(this, 'CostMonitorApi', {
      restApiName: `CostMonitor-${DEPLOYMENT_ID}`,
      description: 'API for cost monitoring',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
    });

    const costResource = costApi.root.addResource('costs');
    costResource.addMethod('GET', new apigateway.LambdaIntegration(costMonitorLambda), {
      authorizer: new apigateway.CognitoUserPoolsAuthorizer(this, 'CostApiAuthorizer', {
        cognitoUserPools: [userPool]
      }),
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // Voice Proxy WebSocket API for Nova Sonic
    const voiceProxyRole = new iam.Role(this, 'VoiceProxyRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
      ],
      inlinePolicies: {
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['bedrock:InvokeModelWithResponseStream', 'bedrock:InvokeModel'],
              resources: [`arn:aws:bedrock:${this.region}::foundation-model/amazon.nova-sonic-v1:0`]
            })
          ]
        })
      }
    });

    const voiceProxyLambda = new lambda.Function(this, 'VoiceProxyLambda', {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambdas', 'voice-proxy')),
      timeout: cdk.Duration.seconds(30),
      role: voiceProxyRole,
      environment: { AWS_REGION_NAME: this.region }
    });

    const voiceWsApi = new cdk.aws_apigatewayv2.CfnApi(this, 'VoiceWebSocketApi', {
      name: `voice-proxy-${DEPLOYMENT_ID}`,
      protocolType: 'WEBSOCKET',
      routeSelectionExpression: '$request.body.action'
    });

    const voiceIntegration = new cdk.aws_apigatewayv2.CfnIntegration(this, 'VoiceIntegration', {
      apiId: voiceWsApi.ref,
      integrationType: 'AWS_PROXY',
      integrationUri: `arn:aws:apigateway:${this.region}:lambda:path/2015-03-31/functions/${voiceProxyLambda.functionArn}/invocations`
    });

    const connectRoute = new cdk.aws_apigatewayv2.CfnRoute(this, 'ConnectRoute', {
      apiId: voiceWsApi.ref,
      routeKey: '$connect',
      target: `integrations/${voiceIntegration.ref}`
    });

    const disconnectRoute = new cdk.aws_apigatewayv2.CfnRoute(this, 'DisconnectRoute', {
      apiId: voiceWsApi.ref,
      routeKey: '$disconnect',
      target: `integrations/${voiceIntegration.ref}`
    });

    const defaultRoute = new cdk.aws_apigatewayv2.CfnRoute(this, 'DefaultRoute', {
      apiId: voiceWsApi.ref,
      routeKey: '$default',
      target: `integrations/${voiceIntegration.ref}`
    });

    const voiceStage = new cdk.aws_apigatewayv2.CfnStage(this, 'VoiceStage', {
      apiId: voiceWsApi.ref,
      stageName: 'prod',
      autoDeploy: true
    });

    voiceProxyLambda.addPermission('WebSocketInvoke', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      sourceArn: `arn:aws:execute-api:${this.region}:${this.account}:${voiceWsApi.ref}/*`
    });

    // Allow Lambda to post back to WebSocket connections
    voiceProxyLambda.addToRolePolicy(new iam.PolicyStatement({
      actions: ['execute-api:ManageConnections'],
      resources: [`arn:aws:execute-api:${this.region}:${this.account}:${voiceWsApi.ref}/*`]
    }));

    const voiceWsUrl = `wss://${voiceWsApi.ref}.execute-api.${this.region}.amazonaws.com/prod`;

    // Outputs
    new cdk.CfnOutput(this, 'RuntimeArn', { value: runtime.agentRuntimeArn, exportName: `${this.stackName}-RuntimeArn` });
    new cdk.CfnOutput(this, 'RuntimeId', { value: runtime.agentRuntimeId, exportName: `${this.stackName}-RuntimeId` });
    new cdk.CfnOutput(this, 'MemoryId', { value: memory.memoryId, exportName: `${this.stackName}-MemoryId` });
    new cdk.CfnOutput(this, 'GatewayUrl', { value: gateway.gatewayUrl, exportName: `${this.stackName}-GatewayUrl` });
    new cdk.CfnOutput(this, 'GatewayId', { value: gateway.gatewayId, exportName: `${this.stackName}-GatewayId` });
    new cdk.CfnOutput(this, 'CaseQueueTableName', { value: caseQueueTable.tableName, exportName: `${this.stackName}-CaseQueueTableName` });
    new cdk.CfnOutput(this, 'CrisisAlertTopicArn', { value: crisisAlertTopic.topicArn, exportName: `${this.stackName}-CrisisAlertTopicArn` });
    new cdk.CfnOutput(this, 'DocumentsBucketName', { value: documentsBucket.bucketName, exportName: `${this.stackName}-DocumentsBucketName` });
    new cdk.CfnOutput(this, 'CostMonitorApiUrl', { value: costApi.url, exportName: `${this.stackName}-CostMonitorApiUrl` });
    new cdk.CfnOutput(this, 'VoiceWebSocketUrl', { value: voiceWsUrl, exportName: `${this.stackName}-VoiceWebSocketUrl` });
  }
}
