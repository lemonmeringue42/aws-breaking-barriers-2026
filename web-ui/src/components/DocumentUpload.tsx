import { useState, useRef } from 'react'
import { fetchAuthSession } from 'aws-amplify/auth'

interface DocumentUploadProps {
  userId: string
  caseRef?: string
  onUploadComplete?: (files: UploadedFile[]) => void
}

interface UploadedFile {
  name: string
  key: string
  url: string
}

const BUCKET_NAME = import.meta.env.VITE_DOCUMENTS_BUCKET || ''
const REGION = import.meta.env.VITE_AWS_REGION || 'us-west-2'

export default function DocumentUpload({ userId, caseRef, onUploadComplete }: DocumentUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    setUploading(true)
    setError(null)

    try {
      const session = await fetchAuthSession()
      const credentials = session.credentials
      
      if (!credentials) {
        throw new Error('Not authenticated')
      }

      const newFiles: UploadedFile[] = []

      for (const file of Array.from(files)) {
        // Validate file type
        const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
        if (!allowedTypes.includes(file.type)) {
          setError(`${file.name}: Only PDF and images allowed`)
          continue
        }

        // Max 5MB
        if (file.size > 5 * 1024 * 1024) {
          setError(`${file.name}: File too large (max 5MB)`)
          continue
        }

        const timestamp = Date.now()
        const safeFileName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_')
        const key = `case-files/${userId}/${caseRef || 'general'}/${timestamp}-${safeFileName}`

        // Upload using presigned URL approach via fetch to S3
        const { S3Client, PutObjectCommand } = await import('@aws-sdk/client-s3')
        
        const s3 = new S3Client({
          region: REGION,
          credentials: {
            accessKeyId: credentials.accessKeyId,
            secretAccessKey: credentials.secretAccessKey,
            sessionToken: credentials.sessionToken,
          }
        })

        const arrayBuffer = await file.arrayBuffer()
        
        await s3.send(new PutObjectCommand({
          Bucket: BUCKET_NAME,
          Key: key,
          Body: new Uint8Array(arrayBuffer),
          ContentType: file.type,
          Metadata: {
            'user-id': userId,
            'case-ref': caseRef || 'general',
            'original-name': file.name
          }
        }))

        newFiles.push({
          name: file.name,
          key,
          url: `s3://${BUCKET_NAME}/${key}`
        })
      }

      setUploadedFiles(prev => [...prev, ...newFiles])
      onUploadComplete?.(newFiles)
      
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (err) {
      console.error('Upload error:', err)
      setError('Upload failed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="ca-document-upload">
      <label className="ca-upload-btn">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          multiple
          onChange={handleFileSelect}
          disabled={uploading}
          style={{ display: 'none' }}
        />
        {uploading ? '⏳ Uploading...' : '📎 Attach Documents'}
      </label>
      
      <span className="ca-upload-hint">PDF or images, max 5MB</span>

      {error && <div className="ca-upload-error">{error}</div>}

      {uploadedFiles.length > 0 && (
        <div className="ca-uploaded-files">
          {uploadedFiles.map((file, i) => (
            <div key={i} className="ca-uploaded-file">
              ✅ {file.name}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
