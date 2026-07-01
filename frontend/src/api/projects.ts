import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export interface Project {
  project_id: string
  name: string
  description: string | null
  created_at: string
}

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const res = await api.get<{ projects: Project[] }>('/projects')
      return res.data.projects
    },
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { name: string; description?: string }) => {
      const res = await api.post<Project>('/projects', body)
      return res.data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (projectId: string) => {
      await api.delete(`/projects/${projectId}`)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}