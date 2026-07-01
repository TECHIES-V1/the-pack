import { useQuery } from '@tanstack/react-query'
import { api } from './client'

export interface MemoryEntry {
  memory_id: string
  content: string
  hunt_id: string
  created_at: string
}

export function useMemory(limit = 50) {
  return useQuery({
    queryKey: ['memory', limit],
    queryFn: async () => {
      const res = await api.get<{ entries: MemoryEntry[] }>('/memory', { params: { limit } })
      return res.data.entries
    },
  })
}
