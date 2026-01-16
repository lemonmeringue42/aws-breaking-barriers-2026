import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, ScanCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb';
import { SESClient, SendEmailCommand } from '@aws-sdk/client-ses';

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({}));
const ses = new SESClient({});

const DEADLINES_TABLE = process.env.DEADLINES_TABLE!;
const APPOINTMENTS_TABLE = process.env.APPOINTMENTS_TABLE!;
const USER_PROFILE_TABLE = process.env.USER_PROFILE_TABLE!;
const FROM_EMAIL = process.env.FROM_EMAIL || 'noreply@citizensadvice.org.uk';

interface Deadline {
  id: string;
  userId: string;
  title: string;
  description?: string;
  dueDate: string;
  category: string;
  priority: string;
  completed?: boolean;
  reminderSent?: boolean;
}

interface Appointment {
  id: string;
  userId: string;
  bureauName?: string;
  scheduledTime: string;
  category: string;
  status: string;
}

async function getUserEmail(userId: string): Promise<string | null> {
  const result = await ddb.send(new ScanCommand({
    TableName: USER_PROFILE_TABLE,
    FilterExpression: 'userId = :uid',
    ExpressionAttributeValues: { ':uid': userId },
  }));
  return result.Items?.[0]?.email || null;
}

async function sendEmail(to: string, subject: string, body: string) {
  await ses.send(new SendEmailCommand({
    Source: FROM_EMAIL,
    Destination: { ToAddresses: [to] },
    Message: {
      Subject: { Data: subject },
      Body: { Html: { Data: body } },
    },
  }));
}

async function checkDeadlines() {
  const now = new Date();
  const threeDaysFromNow = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);

  const result = await ddb.send(new ScanCommand({
    TableName: DEADLINES_TABLE,
    FilterExpression: 'completed <> :true AND (attribute_not_exists(reminderSent) OR reminderSent <> :true)',
    ExpressionAttributeValues: { ':true': true },
  }));

  for (const item of (result.Items || []) as Deadline[]) {
    const dueDate = new Date(item.dueDate);
    if (dueDate <= threeDaysFromNow && dueDate >= now) {
      const email = await getUserEmail(item.userId);
      if (email) {
        const daysUntil = Math.ceil((dueDate.getTime() - now.getTime()) / (24 * 60 * 60 * 1000));
        await sendEmail(email, `Reminder: ${item.title} due in ${daysUntil} day(s)`,
          `<h2>Upcoming Deadline</h2>
          <p><strong>${item.title}</strong> is due on ${dueDate.toLocaleDateString('en-GB')}.</p>
          <p>${item.description || ''}</p>
          <p>Category: ${item.category} | Priority: ${item.priority}</p>`
        );
        await ddb.send(new UpdateCommand({
          TableName: DEADLINES_TABLE,
          Key: { id: item.id },
          UpdateExpression: 'SET reminderSent = :true',
          ExpressionAttributeValues: { ':true': true },
        }));
      }
    }
  }
}

async function checkAppointmentFollowups() {
  const now = new Date();
  const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  const result = await ddb.send(new ScanCommand({
    TableName: APPOINTMENTS_TABLE,
    FilterExpression: '#status = :completed',
    ExpressionAttributeNames: { '#status': 'status' },
    ExpressionAttributeValues: { ':completed': 'completed' },
  }));

  for (const item of (result.Items || []) as Appointment[]) {
    const appointmentTime = new Date(item.scheduledTime);
    if (appointmentTime <= now && appointmentTime >= oneDayAgo) {
      const email = await getUserEmail(item.userId);
      if (email) {
        await sendEmail(email, 'How did your appointment go?',
          `<h2>Follow-up: Your Recent Appointment</h2>
          <p>You had an appointment${item.bureauName ? ` at ${item.bureauName}` : ''} regarding ${item.category}.</p>
          <p>How did it go? If you need further assistance, please log in to continue your conversation with our advisor.</p>`
        );
      }
    }
  }
}

export const handler = async () => {
  await checkDeadlines();
  await checkAppointmentFollowups();
  return { statusCode: 200, body: 'Notifications processed' };
};
