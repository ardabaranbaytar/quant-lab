import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ResultView } from '../components/ResultView'
import { ErrorBanner, Spinner } from '../components/ui'
import { useI18n } from '../i18n/context'
import { api, type BacktestDetail } from '../lib/api'

export function RunPage() {
  const { t } = useI18n()
  const { id } = useParams()
  const [run, setRun] = useState<BacktestDetail | null>(null)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    api.backtest(Number(id)).then(setRun).catch(setError)
  }, [id])

  return (
    <div className="space-y-4">
      <Link to="/history" className="text-xs text-muted hover:text-ink">{t.history.allRuns}</Link>
      {error ? <ErrorBanner error={error} /> : run ? <ResultView run={run} showPermalink={false} /> : <Spinner />}
    </div>
  )
}
