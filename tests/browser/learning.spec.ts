import { execFileSync } from 'node:child_process'
import { test, expect } from '@playwright/test'

test('two identities share material and retain private sessions, Playground and revocable sharing', async ({ page, browser }) => {
  await page.goto('/')
  await expect(page.getByRole('button', { name: '+ New study space' })).toHaveCount(0)
  expect((await page.request.post('/api/offerings', { data: { code: 'FORGED', title: 'Forbidden', year: 2026, semester: 'Semester 2' } })).status()).toBe(403)
  const invite = execFileSync('apps/api/.venv/bin/python', ['-m', 'athena_api.spaces.cli', 'create-lecturer-invite'], { env: { ...process.env, ATHENA_DB: process.env.ATHENA_E2E_DB! } }).toString().trim()
  await page.getByText('Lecturer access', { exact: true }).click()
  await page.getByLabel('Lecturer invite code').fill(invite)
  await page.getByRole('button', { name: 'Enable lecturer access' }).click()
  await page.getByRole('button', { name: '+ New study space' }).click()
  await page.getByLabel('Unit code', { exact: true }).fill(`E2E${Date.now()}`)
  await page.getByLabel('Unit title', { exact: true }).fill('Synthetic browser acceptance')
  await page.getByRole('button', { name: 'Create study space', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Study space/ })).toBeVisible()
  const offering = page.url().split('/units/')[1].split('/')[0]
  await page.getByLabel('Upload material', { exact: false }).setInputFiles({ name: 'synthetic-notes.txt', mimeType: 'text/plain', buffer: Buffer.from('Bubble Sort compares adjacent values and swaps them when out of order. Repeating passes sorts the list.') })
  await expect(page.getByRole('button', { name: 'Publish document' })).toBeVisible({ timeout: 20000 })
  await page.getByRole('button', { name: 'Publish document' }).click()
  await page.getByRole('button', { name: 'Publish study space' }).click()
  await page.getByRole('radio', { name: 'Student', exact: true }).click()
  await page.goto(`/units/${offering}`)
  await page.getByLabel('What do you want to learn?').fill('Bubble Sort')
  // Lose the response after the server commits the opening session. Recovery
  // must open that session, even if the student has since edited their goal.
  let loseStartResponse = true
  await page.route(`**/api/units/${offering}/sessions`, async (route) => {
    if (route.request().method() === 'POST' && loseStartResponse) {
      loseStartResponse = false
      const response = await route.fetch()
      expect(response.ok()).toBeTruthy()
      await route.abort('failed')
    } else await route.continue()
  })
  await page.getByRole('button', { name: 'Start session', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Recover previous session', exact: true })).toBeVisible()
  await page.getByLabel('What do you want to learn?').fill('A different goal')
  await expect(page.getByRole('button', { name: 'Start session', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Recover previous session', exact: true }).click()
  await expect(page.getByText('Which relationship underlies bubble-sort?', { exact: true })).toBeVisible()
  const recoveredSessions = await (await page.request.get(`/api/units/${offering}/sessions`)).json()
  expect(recoveredSessions).toHaveLength(1)
  expect(recoveredSessions[0].goal).toBe('Bubble Sort')
  const sessionURL = page.url()
  const other = await browser.newContext()
  const outsider = await other.newPage()
  await outsider.goto('/')
  await expect(outsider.getByRole('button', { name: '+ New study space' })).toHaveCount(0)
  await outsider.goto(sessionURL)
  await expect(outsider.getByRole('heading', { name: 'Session not found' })).toBeVisible()
  await outsider.goto(`/units/${offering}`)
  await expect(outsider.getByLabel('What do you want to learn?')).toBeVisible()
  // Complete the actual adaptive fixture through the browser, including retry replay.
  const sessionId = sessionURL.split('/s/')[1]
  const before = await (await page.request.get(`/api/units/${offering}/sessions/${sessionId}`)).json()
  const question = before.messages[0].activity.question
  const choice = question.choices.find((c: { choice_id: string }) => c.choice_id === 'b')
  await page.getByRole('button', { name: choice.text, exact: true }).click()
  await expect(page.getByRole('button', { name: 'Continue', exact: true })).toBeVisible()
  const replay = await page.request.post(`/api/units/${offering}/sessions/${sessionId}/answers`, { data: { question_id: question.question_id, choice_id: 'b', shown: choice.text } })
  expect(replay.ok()).toBeTruthy()
  await page.getByRole('button', { name: 'Continue', exact: true }).click()
  // Test dictation as a draft: permission errors, cancellation and review. The
  // provider is intercepted; real transcription has a separate opt-in live pass.
  await page.evaluate(() => {
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {
      getUserMedia: async () => { throw new DOMException('denied', 'NotAllowedError') },
    } })
  })
  await page.getByLabel('Your answer', { exact: true }).fill('My draft')
  await page.getByRole('button', { name: 'Speak answer' }).click()
  await expect(page.getByText('Microphone access was denied.', { exact: false })).toBeVisible()
  await expect(page.getByLabel('Your answer', { exact: true })).toHaveValue('My draft')
  await page.evaluate(() => {
    const media = { getTracks: () => [{ stop() {} }] }
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: async () => media } })
    class Recorder {
      static isTypeSupported() { return true }
      state = 'inactive'
      ondataavailable: ((event: { data: Blob }) => void) | null = null
      onstop: (() => void) | null = null
      start() { this.state = 'recording' }
      stop() {
        this.state = 'inactive'
        this.ondataavailable?.({ data: new Blob(['synthetic audio']) })
        this.onstop?.()
      }
    }
    Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: Recorder })
  })
  let transcriptions = 0
  await page.route('**/transcriptions', async route => {
    transcriptions++
    await route.fulfill({ json: { text: 'I compare and swap neighbours.' } })
  })
  await page.getByRole('button', { name: 'Speak answer' }).click()
  await expect(page.getByRole('button', { name: 'Answer', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Cancel voice typing' }).click()
  expect(transcriptions).toBe(0)
  await expect(page.getByLabel('Your answer', { exact: true })).toHaveValue('My draft')
  await page.getByRole('button', { name: 'Speak answer' }).click()
  await page.getByRole('button', { name: /Stop recording/ }).waitFor()
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { configurable: true, value: true })
    document.dispatchEvent(new Event('visibilitychange'))
    Reflect.deleteProperty(document, 'hidden')
  })
  await expect(page.getByText('Recording cancelled when you left the tab.', { exact: false })).toBeVisible()
  expect(transcriptions).toBe(0)
  await page.getByRole('button', { name: 'Speak answer' }).click()
  await page.getByRole('button', { name: /Stop recording/ }).click()
  await expect(page.getByLabel('Your answer', { exact: true })).toHaveValue('My draft I compare and swap neighbours.')
  await expect(page.getByText('Transcript added.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Answer', exact: true })).toBeInViewport()
  expect(transcriptions).toBe(1)
  await page.getByLabel('Your answer', { exact: true }).fill('I compare and swap neighbours.')
  await page.getByRole('button', { name: 'Answer', exact: true }).click()
  await expect(page.getByLabel('Your answer', { exact: true })).toHaveValue('')
  await page.getByLabel('Your answer', { exact: true }).fill('The larger value moves right with each adjacent comparison.')
  await page.getByRole('button', { name: 'Answer', exact: true }).click()
  await expect(page.getByText('✓ Session goal reached', { exact: true })).toBeVisible()
  await page.goto(`/units/${offering}/practice`)
  await expect(page.getByRole('button', { name: 'Check answer', exact: true })).toBeVisible()
  const options = page.getByRole('radiogroup', { name: 'Answer options' })
  if (await options.count()) await options.getByRole('radio').first().click()
  else await page.getByLabel('Your answer', { exact: true }).fill('Compare 3 and 1, swap them; compare 3 and 2, swap them. The pass gives [1, 2, 3].')
  await page.getByRole('button', { name: 'Check answer', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Good', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Good', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Good', exact: true }).click()
  await page.goto(`/units/${offering}/library`)
  await page.getByRole('button', { name: 'Read source', exact: true }).click()
  await expect(page.getByText('Bubble Sort compares adjacent values and swaps them when out of order.', { exact: false })).toBeVisible()
  await page.goto(sessionURL)
  await page.getByRole('link', { name: /Playground/ }).click()
  await expect(page.getByText('The Playground is empty. Ask the tutor a question and it will set up an experiment here.', { exact: true })).toBeVisible()
  await page.getByLabel('Message Athena').fill('Build a Python experiment')
  await page.getByRole('button', { name: 'Send message', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Python multiplication' })).toBeVisible({ timeout: 20000 })
  await expect(page.getByText('Experiment is ready. Explain why the output is 42.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: '▶ Run', exact: true }).click()
  await expect(page.getByText('Python: finished · verified execution', { exact: true })).toBeVisible({ timeout: 20000 })
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Python multiplication' })).toBeVisible()
  await expect(page.getByText('Python: finished · verified execution', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Back to chat' }).click()
  await page.getByRole('button', { name: 'Share with lecturer…' }).click()
  await expect(page.getByLabel('Shared session preview')).toContainText('Build a Python experiment')
  await page.getByRole('button', { name: 'Share anonymously', exact: true }).click()
  const shared = await page.request.get(`/api/units/${offering}/shared-sessions`)
  const [share] = await shared.json()
  expect(JSON.stringify(share)).not.toContain(sessionURL.split('/s/')[1])
  await page.getByRole('button', { name: 'Stop sharing' }).click()
  expect((await page.request.get(`/api/units/${offering}/shared-sessions/${share.share_id}`)).status()).toBe(404)
  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await page.goto(sessionURL)
  await expect(page.getByRole('heading', { name: 'Session not found' })).toBeVisible()
  await other.close()
})
