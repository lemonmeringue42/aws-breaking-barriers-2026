import { BedrockRuntimeClient, InvokeModelCommand } from '@aws-sdk/client-bedrock-runtime';
import { fetchAuthSession } from 'aws-amplify/auth';

let bedrockClient: BedrockRuntimeClient | null = null;

async function getClient(): Promise<BedrockRuntimeClient> {
  if (!bedrockClient) {
    const session = await fetchAuthSession();
    bedrockClient = new BedrockRuntimeClient({
      region: import.meta.env.VITE_AWS_REGION || 'us-west-2',
      credentials: session.credentials,
    });
  }
  return bedrockClient;
}

export async function translateText(text: string, targetLang: string): Promise<string> {
  if (targetLang === 'en' || !text.trim()) return text;
  
  const langName = SUPPORTED_LANGUAGES.find(l => l.code === targetLang)?.name || targetLang;
  
  try {
    const client = await getClient();
    const command = new InvokeModelCommand({
      modelId: 'anthropic.claude-3-haiku-20240307-v1:0',
      contentType: 'application/json',
      body: JSON.stringify({
        anthropic_version: 'bedrock-2023-05-31',
        max_tokens: 4096,
        messages: [{
          role: 'user',
          content: `Translate the following text to ${langName}. Keep all formatting (markdown, bullet points, etc). Only output the translation, nothing else.\n\n${text}`
        }]
      })
    });
    
    const response = await client.send(command);
    const result = JSON.parse(new TextDecoder().decode(response.body));
    return result.content?.[0]?.text || text;
  } catch (error) {
    console.error('Translation failed:', error);
    return text;
  }
}

export const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'cy', name: 'Welsh', flag: '🏴󠁧󠁢󠁷󠁬󠁳󠁿' },
  { code: 'pl', name: 'Polish', flag: '🇵🇱' },
  { code: 'ur', name: 'Urdu', flag: '🇵🇰' },
  { code: 'bn', name: 'Bengali', flag: '🇧🇩' },
  { code: 'gu', name: 'Gujarati', flag: '🇮🇳' },
  { code: 'pa', name: 'Punjabi', flag: '🇮🇳' },
  { code: 'ar', name: 'Arabic', flag: '🇸🇦' },
  { code: 'zh', name: 'Chinese', flag: '🇨🇳' },
  { code: 'ro', name: 'Romanian', flag: '🇷🇴' },
];
