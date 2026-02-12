import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import NotFoundPage from '../../pages/NotFoundPage'

function renderPage() {
  return render(
    <BrowserRouter>
      <NotFoundPage />
    </BrowserRouter>
  )
}

describe('NotFoundPage', () => {
  it('renders 404 text', () => {
    renderPage()
    expect(screen.getByText('404')).toBeInTheDocument()
  })

  it('renders page not found message', () => {
    renderPage()
    expect(screen.getByText('Page Not Found')).toBeInTheDocument()
  })

  it('has a Go Back button', () => {
    renderPage()
    expect(screen.getByText('Go Back')).toBeInTheDocument()
  })

  it('has a Dashboard link', () => {
    renderPage()
    const link = screen.getByText('Dashboard')
    expect(link.closest('a')).toHaveAttribute('href', '/')
  })
})
