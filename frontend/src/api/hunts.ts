import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export interface HuntSummary {
  hunt_id: string
  state: string
  source: string
  raw_input: string
  strategy: string | null
  boundary_usd: number
  created_at: string
  last_seq: number
  project_id: string | null
}

export interface HuntListResponse {
  hunts: HuntSummary[]
  next_cursor: string | null
}

export interface IntakePayload {
  text?: string
  artifact_ids?: string[]
}

export interface IntakeResponse {
  reply: string
  ready: boolean
  brief: string
}

export function useHunts(projectId?: string, limit = 20) {
  return useQuery({
    queryKey: ['hunts', projectId, limit],
    queryFn: async () => {
      const params: Record<string, string | number> = { limit }
      if (projectId) params.project_id = projectId
      const res = await api.get<HuntListResponse>('/hunts', { params })
      return res.data
    },
  })
}

export function useHunt(huntId: string | null) {
  return useQuery({
    queryKey: ['hunts', huntId],
    queryFn: async () => {
      const res = await api.get<HuntSummary>(`/hunts/${huntId}`)
      return res.data
    },
    enabled: !!huntId,
  })
}

export function useIntake() {
  return useMutation({
    mutationFn: async (body: IntakePayload) => {
      const res = await api.post<IntakeResponse>('/hunts/intake', body)
      return res.data
    },
  })
}

export function useCreateHunt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { input: string; strategy?: string; project_id?: string; boundary_usd?: number }) => {
      const res = await api.post<{ hunt_id: string }>('/hunts', body)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['hunts'] })
    },
  })
}

export function useApprovePlan(huntId: string) {
  return useMutation({
    mutationFn: async (body: { mode: 'wild' | 'on_signal' | 'on_command'; boundary_usd: number }) => {
      await api.post(`/hunts/${huntId}/plan/approve`, body)
    },
  })
}

export function useStopHunt(huntId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.post(`/hunts/${huntId}/stop`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['hunts', huntId] })
    },
  })
}

export function useResolveHold(huntId: string) {
  return useMutation({
    mutationFn: async ({ holdId, resolution }: { holdId: string; resolution: string }) => {
      await api.post(`/hunts/${huntId}/holds/${holdId}/resolve`, { resolution })
    },
  })
}

export function useDeleteHunt(huntId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      await api.delete(`/hunts/${huntId}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['hunts'] })
    },
  })
}

export function useHuntMessages(huntId: string) {
  return useQuery({
    queryKey: ['hunts', huntId, 'messages'],
    queryFn: async () => {
      const res = await api.get<{ messages: unknown[] }>(`/hunts/${huntId}/messages`)
      return res.data.messages
    },
    enabled: !!huntId,
  })
}

export function useHuntArtifacts(huntId: string) {
  return useQuery({
    queryKey: ['hunts', huntId, 'artifacts'],
    queryFn: async () => {
      const res = await api.get<{ artifacts: unknown[] }>(`/hunts/${huntId}/artifacts`)
      return res.data.artifacts
    },
    enabled: !!huntId,
  })
}

export function useSpendSummary() {
  return useQuery({
    queryKey: ['spend'],
    queryFn: async () => {
      const res = await api.get<unknown[]>('/hunts/spend/summary')
      return res.data
    },
  })
}