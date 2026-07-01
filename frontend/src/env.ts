import { z } from 'zod'

const EnvSchema = z.object({
  VITE_ENGINE_URL: z.string().url().default('http://localhost:8000'),
  VITE_GATEWAY_URL: z.string().default('ws://localhost:8080'),
})

export const env = EnvSchema.parse(import.meta.env)