import * as RadixToast from '@radix-ui/react-toast'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export const ToastProvider = RadixToast.Provider
export const ToastViewport = () => (
  <RadixToast.Viewport className="fixed bottom-4 right-4 z-[100] flex max-h-screen w-[380px] flex-col gap-2 outline-none" />
)

interface ToastProps extends RadixToast.ToastProps {
  variant?: 'default' | 'warn' | 'danger' | 'success'
  title: string
  description?: string
}

export function Toast({ variant = 'default', title, description, className, ...props }: ToastProps) {
  return (
    <RadixToast.Root
      className={cn(
        'pointer-events-auto flex w-full items-start gap-3 rounded-lg border p-4 shadow-lg',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:fade-out-80 data-[state=open]:fade-in-0',
        'data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-right-full',
        {
          default: 'border-border bg-surface',
          warn: 'border-warn/30 bg-surface',
          danger: 'border-danger/30 bg-surface',
          success: 'border-success/30 bg-surface',
        }[variant],
        className,
      )}
      {...props}
    >
      <div className="flex-1 gap-1">
        <RadixToast.Title
          className={cn('text-sm font-semibold', {
            default: 'text-text',
            warn: 'text-warn',
            danger: 'text-danger',
            success: 'text-success',
          }[variant])}
        >
          {title}
        </RadixToast.Title>
        {description && (
          <RadixToast.Description className="mt-0.5 text-xs text-text-dim">
            {description}
          </RadixToast.Description>
        )}
      </div>
      <RadixToast.Close className="shrink-0 rounded-sm opacity-50 hover:opacity-100">
        <X className="h-4 w-4 text-text-dim" />
      </RadixToast.Close>
    </RadixToast.Root>
  )
}
