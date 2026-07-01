import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export interface Instinct {
  instinct_id: string
  name: string
  description: string | null
  plan_template: unknown
  created_at: string
}

export function useInstincts() {
  return useQuery({
    queryKey: ['instincts'],
    queryFn: async () => {
      const res = await api.get<{ instincts: Instinct[] }>('/instincts')
      return res.data.instincts
    },
  })
}

export function useCreateInstinct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string; plan_template: unknown }) => {
      const res = await api.post<Instinct>('/instincts', body)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['instincts'] })
    },
  })
}

export function useDeleteInstinct() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (instinctId: string) => {
      await api.delete(`/instincts/${instinctId}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['instincts'] })
    },
  })
}
