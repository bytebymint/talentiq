# HR review workflow

Start on **Overview**. The next-step card walks through defining a role, adding CVs and preparing reviews. Select the hiring project there. **Refresh CV reviews** explicitly re-evaluates CVs that need the current pipeline; previous results are preserved in evaluation history. Completed reviews are saved as they finish.

Open a candidate's **CV brief** to see a source-linked summary, work history, demonstrated versus listed skills, education, credentials, achievements, clarification points and interview questions. **Check role match** opens the rubric assessment. **Human review** holds the reviewer's own notes and next steps. Old evaluations without a current brief keep their earlier assessment available and offer **Review this CV**.

The Balanced/QwenCloud pipeline reads the original passages, builds a proposed brief and assessment, then makes a second model call to check both against the same source text. The server also matches quoted evidence to original document/page passages. Personal projects, product vendors, employers, qualifications and team contributions are distinguished in the instructions. Source checking verifies the reading of a CV; it does not independently authenticate its claims.

Open a candidate's Copilot tab, or open Talent Search → Recruitment copilot and choose a candidate. A CV-review question is already filled in. Edit it if needed and select **Ask copilot**.

Five tasks prepare questions without sending a request until HR chooses to send:

- **Review CV**: overview, documented strengths, details to clarify and interview questions. With multiple CVs, this becomes **Compare CVs** and uses the same dimensions for each person.
- **Match to role**: evidence against required and preferred requirements.
- **Interview questions**: five focused questions, with the claim or gap each question should clarify.
- **Hiring review**: required/preferred requirement evidence, relevant strengths, partial matches, gaps and details to verify before a human decision. Asking “Should we hire this candidate?” receives this useful assessment without an AI hire/reject verdict.
- **Work experience**: employers, titles, dates and responsibilities, separating employment from other projects.

**HR instructions · ready to use** contains editable answer preferences. Defaults ask for plain language, concise answers, clear unknowns and citations. Restore defaults with one action. Preferences cannot override the server's evidence rules. Each new project conversation starts with the defaults.

The copilot always receives the role description, requirements, evaluation language and profile review instructions. It keeps each candidate's original pages labeled, cites claims, distinguishes listed skills from demonstrated experience, and flags missing or conflicting details. It does not create hiring probabilities or make final hiring decisions. Large selections can use excerpts and explicitly disclose that coverage.

The copilot holds its first draft privately, shows a source-checking stage, and publishes the corrected answer only after a second model review. A failed check is shown as an error and the draft is not saved as an answer. Finished answers carry **Answer checked against CV sources**. Checked briefs are source-fingerprinted and cannot be reused after the underlying CV changes. Original pages remain authoritative and available to the model for detailed follow-up questions.

The extra review call increases latency. There is no guaranteed one-minute processing time or measured “5× intelligence” claim. Fast local screening remains a lighter, separate mode; choose Balanced for these richer CV briefs. The same model can repeat a mistake across both passes, so HR should still inspect important source links.

New recruitment profiles contain review instructions and criterion definitions. The **Guide the CV review** step presents HR guidance first; model and depth controls are under **Advanced AI settings**. Existing profile versions keep their saved instructions. The updated full-CV pipeline marks previous evaluations stale so HR can intentionally rerun them; it does not silently rewrite saved results.

Local AI and QwenCloud use the same HR guidance. Provider selection and cloud disclosure continue to apply. Only the selected provider handles AI requests.

## Record the HR outcome

In a candidate’s **Human review** tab, choose **Hire**, **Hold** or **Reject**. These select the existing Hired, On Hold or Not Selected pipeline stages; they do not save immediately. Add your own note and select **Save human review**. Hire and Reject require explicit human confirmation plus a nonblank rationale. Successful saves record the authenticated reviewer and audit the change. A failed save keeps the draft note available to retry.

The same controls and prepared question are available in Persian. Re-analysis preserves human review stages and hiring outcomes, including when inference fails. Chat does not update status, shortlist or notes.

Opening or closing a candidate while a save completes does not reopen a closed dialog or replace another candidate’s review.
