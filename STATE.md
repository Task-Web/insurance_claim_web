# Insurance Claim State

The backend stores per-user state keyed by the `user_id` cookie. The task 005
frontend writes draft data to `data.current_claim` while the user is working and
one entry to `data.submitted_claims` for each submitted claim.

The frontend syncs state-changing user operations to the backend in near real
time through `PATCH /api/state`. The browser cache is only a fallback; success
page data and evaluation reads prefer backend state.

Each claim contains:

- `formData`: field values collected from the insurance form.
- `uploadedFiles`: metadata returned by `/api/files`, including `originalName`,
  `name`, `url`, and the stored backend `filename`.
- `currentStep`: current form step for in-progress drafts.
- `submittedAt`: ISO timestamp.
