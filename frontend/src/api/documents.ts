import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export interface Document {
  doc_id: string
  filename: string
  kind: string
  size_bytes: number
  created_at: string
  summary: string | null
}

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: async () => {
      const res = await api.get<{ documents: Document[] }>('/documents')
      return res.data.documents
    },
  })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post<Document>('/documents', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function useDeleteDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (docId: string) => {
      await api.delete(`/documents/${docId}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}