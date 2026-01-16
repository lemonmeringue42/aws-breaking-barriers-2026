import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  // Case model for advisor dashboard
  Case: a
    .model({
      caseId: a.string().required(),
      userId: a.string().required(),
      sessionId: a.string(),
      urgencyLevel: a.enum(['CRISIS', 'URGENT', 'STANDARD', 'GENERAL']),
      priority: a.integer(),
      issueCategory: a.string(),
      timeSensitivity: a.string(),
      summary: a.string(),
      status: a.enum(['PENDING', 'IN_PROGRESS', 'RESOLVED', 'CLOSED']),
      assignedAdvisor: a.string(),
      advisorNotes: a.string(),
      createdAt: a.datetime(),
      scheduledCallbackTime: a.datetime(),
      lastUpdated: a.datetime(),
    })
    .authorization((allow) => [
      allow.authenticated(),
    ])
    .identifier(['caseId']),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
});
