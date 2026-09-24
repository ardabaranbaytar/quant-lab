import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ResultView } from '../components/ResultView'
import { ErrorBanner, Spinner } from '../components/ui'
import { api, type BacktestDetail } from '../lib/api'

export function RunPage() {
  const { id } = useParams()
  const [run, setRun] = useState<BacktestDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.backtest(Number(id)).then(setRun).catch((e: Error) => setError(e.message))
  }, [id])

  return (
    <div className="space-y-4">
      <Link to="/history" className="text-xs text-muted hover:text-ink">← All runs</Link>
      {error ? <ErrorBanner message={error} /> : run ? <ResultView run={run} showPermalink={false} /> : <Spinner />}
    </div>
  )
}
