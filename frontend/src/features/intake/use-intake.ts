import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useIntake, useCreateHunt } from '@/api/hunts'

export type Role = 'user' | 'alpha'

export type Message = {
  id: string
  role: Role
  text: string
  isThinking?: boolean
}

export type AttachedFile = {
  localId: string
  file: File
  name: string
}

let _msgId = 0
function nextId() {
  return String(++_msgId)
}

export function useIntakeLogic() {
  const navigate = useNavigate()
  const { mutateAsync: sendToAlpha, isPending } = useIntake()
  const { mutateAsync: createHunt } = useCreateHunt()

  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
  const [isDragging, setIsDragging] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`
  }, [input])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const addFiles = useCallback((files: FileList | File[]) => {
    const incoming = Array.from(files).map((f) => ({
      localId: nextId(),
      file: f,
      name: f.name,
    }))
    setAttachedFiles((prev) => [...prev, ...incoming])
  }, [])

  const removeFile = useCallback((localId: string) => {
    setAttachedFiles((prev) => prev.filter((f) => f.localId !== localId))
  }, [])

  const pickFiles = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  const send = useCallback(async () => {
    const text = input.trim()
    if (!text && attachedFiles.length === 0) return

    const fileNote = attachedFiles.map((f) => `[${f.name}]`).join(' ')
    const builtText = [text, fileNote].filter(Boolean).join(' ')

    const thinkingId = nextId()
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: 'user', text: builtText },
      { id: thinkingId, role: 'alpha', text: '', isThinking: true },
    ])
    setInput('')
    setAttachedFiles([])

    try {
      const res = await sendToAlpha({ text: builtText })

      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId ? { ...m, text: res.reply, isThinking: false } : m,
        ),
      )

      if (res.ready) {
        const hunt = await createHunt({ input: res.brief })
        navigate(`/hunts/${hunt.hunt_id}`)
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === thinkingId
            ? { ...m, text: 'Something went wrong. Try again.', isThinking: false }
            : m,
        ),
      )
      console.error('[intake]', err)
    }
  }, [input, attachedFiles, sendToAlpha, createHunt, navigate])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        void send()
      }
    },
    [send],
  )

  // Drag handlers attached to the outer container
  const onDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const onDragLeave = useCallback((e: React.DragEvent) => {
    if (!e.relatedTarget || !(e.currentTarget as Element).contains(e.relatedTarget as Node)) {
      setIsDragging(false)
    }
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      if (e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files)
      }
    },
    [addFiles],
  )

  return {
    messages,
    input,
    setInput,
    attachedFiles,
    removeFile,
    isDragging,
    isPending,
    send,
    pickFiles,
    addFiles,
    fileInputRef,
    textareaRef,
    messagesEndRef,
    handleKeyDown,
    onDragEnter,
    onDragOver,
    onDragLeave,
    onDrop,
  }
}
