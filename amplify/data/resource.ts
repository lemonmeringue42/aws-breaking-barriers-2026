import { type ClientSchema, a, defineData } from '@aws-amplify/backend'

const schema = a.schema({
  // User table - links to Cognito
  User: a.model({
    id: a.string().required(),
    sessions: a.hasMany('ChatSession', 'userId'),
    feedback: a.hasMany('Feedback', 'userId'),
    profiles: a.hasMany('UserProfile', 'userId'),
    appointments: a.hasMany('Appointment', 'userId'),
    deadlines: a.hasMany('Deadline', 'userId'),
    documents: a.hasMany('Document', 'userId'),
    benefitsCalculations: a.hasMany('BenefitsCalculation', 'userId'),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [allow.owner()]),

  // Chat Session model
  ChatSession: a.model({
    id: a.id().required(),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    title: a.string(),
    messages: a.hasMany('ChatMessage', 'sessionId'),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Chat Message model
  ChatMessage: a.model({
    id: a.id().required(),
    sessionId: a.id().required(),
    session: a.belongsTo('ChatSession', 'sessionId'),
    role: a.enum(['user', 'assistant']),
    content: a.string().required(),
    timestamp: a.datetime(),
    feedback: a.hasMany('Feedback', 'messageId'),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Feedback model
  Feedback: a.model({
    id: a.id().required(),
    messageId: a.id().required(),
    message: a.belongsTo('ChatMessage', 'messageId'),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    feedback: a.enum(['up', 'down']),
    comment: a.string(),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // UserProfile model - includes location for local advice routing
  UserProfile: a.model({
    id: a.id().required(),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    name: a.string(),
    email: a.string(),
    postcode: a.string(),
    region: a.string(),
    localBureauId: a.string(),
    notes: a.string(),
    onboardingCompleted: a.boolean(),
    preferences: a.json(),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Notes model - for saving advice case notes
  Notes: a.model({
    id: a.id().required(),
    userId: a.string().required(),
    content: a.string().required(),
    category: a.string(),
    actionRequired: a.boolean(),
    deadline: a.string(),
    resolved: a.boolean(),
  })
  .authorization((allow) => [allow.authenticated()])
  .secondaryIndexes((index) => [
    index('userId')
  ]),

  // LocalBureau model - Citizens Advice bureau locations
  LocalBureau: a.model({
    id: a.id().required(),
    name: a.string().required(),
    region: a.string().required(),
    postcodes: a.string(),
    address: a.string(),
    phone: a.string(),
    email: a.string(),
    openingHours: a.string(),
    specialisms: a.string(),
    knowledgeBaseId: a.string(),
  })
  .authorization((allow) => [allow.authenticated().to(['read'])]),

  // Appointment model - scheduled calls with advisors
  Appointment: a.model({
    id: a.id().required(),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    bureauId: a.string(),
    bureauName: a.string(),
    advisorName: a.string(),
    scheduledTime: a.datetime().required(),
    duration: a.integer(),
    urgencyScore: a.integer().required(),
    category: a.string().required(),
    caseNotes: a.string(),
    status: a.enum(['scheduled', 'completed', 'cancelled', 'noshow']),
    phoneNumber: a.string(),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Deadline model - track important dates
  Deadline: a.model({
    id: a.id().required(),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    title: a.string().required(),
    description: a.string(),
    dueDate: a.datetime().required(),
    category: a.string().required(),
    priority: a.enum(['low', 'medium', 'high', 'urgent']),
    completed: a.boolean(),
    reminderSent: a.boolean(),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // Document model - generated letters and forms
  Document: a.model({
    id: a.id().required(),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    title: a.string().required(),
    type: a.string().required(),
    content: a.string().required(),
    category: a.string(),
    s3Key: a.string(),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

  // BenefitsCalculation model - store calculation results
  BenefitsCalculation: a.model({
    id: a.id().required(),
    userId: a.id().required(),
    user: a.belongsTo('User', 'userId'),
    income: a.json(),
    expenses: a.json(),
    circumstances: a.json(),
    results: a.json(),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
  })
  .authorization((allow: any) => [
    allow.owner(),
    allow.authenticated().to(['read']),
  ]),

})

export type Schema = ClientSchema<typeof schema>

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
})
