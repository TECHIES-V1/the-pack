import axios from 'axios'
import { env } from '@/env'

export const api = axios.create({
  baseURL: env.VITE_ENGINE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

api.interceptors.response.use(
  (res) => res,
  (err: unknown) => {
    if (axios.isAxiosError(err)) {
      const msg = (err.response?.data as { detail?: string })?.detail ?? err.message
      return Promise.reject(new Error(msg))
    }
    return Promise.reject(err)
  },
)