import { createBrowserRouter } from 'react-router-dom'
import { lazy, Suspense } from 'react'

function Loading() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-border border-t-accent" />
    </div>
  )
}

function wrap(Component: React.ComponentType) {
  return (
    <Suspense fallback={<Loading />}>
      <Component />
    </Suspense>
  )
}

const IntakePage     = lazy(() => import('@/features/intake/intake-page'))
const TerritoryPage  = lazy(() => import('@/features/territory/territory-page'))
const DenPage        = lazy(() => import('@/features/den/den-page'))
const ArtifactsPage  = lazy(() => import('@/features/artifacts/artifacts-page'))
const TracksPage     = lazy(() => import('@/features/tracks/tracks-page'))
const ScorecardPage  = lazy(() => import('@/features/scorecard/scorecard-page'))
const LibraryPage    = lazy(() => import('@/features/library/library-page'))
const InstinctsPage  = lazy(() => import('@/features/instincts/instincts-page'))
const MemoryPage     = lazy(() => import('@/features/memory/memory-page'))
const SpendPage      = lazy(() => import('@/features/spend/spend-page'))

export const router = createBrowserRouter([
  { path: '/',                          element: wrap(IntakePage) },
  { path: '/hunts/:huntId',             element: wrap(TerritoryPage) },
  { path: '/hunts/:huntId/den',         element: wrap(DenPage) },
  { path: '/hunts/:huntId/artifacts',   element: wrap(ArtifactsPage) },
  { path: '/hunts/:huntId/tracks',      element: wrap(TracksPage) },
  { path: '/hunts/:huntId/scorecard',   element: wrap(ScorecardPage) },
  { path: '/library',                   element: wrap(LibraryPage) },
  { path: '/instincts',                 element: wrap(InstinctsPage) },
  { path: '/memory',                    element: wrap(MemoryPage) },
  { path: '/spend',                     element: wrap(SpendPage) },
])
