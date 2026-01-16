#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import * as fs from 'fs';
import { NotesStack } from './notes-stack';
import { PricingMcpStack } from './pricing-stack';

const deploymentConfig = JSON.parse(fs.readFileSync('../../deployment-config.json', 'utf-8'));
const DEPLOYMENT_ID = deploymentConfig.deploymentId;

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-west-2'
};

new NotesStack(app, `NotesStack-${DEPLOYMENT_ID}`, {
  env,
  description: `Notes MCP Server - User notes management (${DEPLOYMENT_ID})`
});

new PricingMcpStack(app, `PricingStack-${DEPLOYMENT_ID}`, {
  env,
  deploymentId: DEPLOYMENT_ID,
  description: `AWS Pricing MCP Server - Real-time pricing data (${DEPLOYMENT_ID})`
});

app.synth();
