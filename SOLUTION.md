# Solution Steps

1. Add DRF pagination in `project/settings.py` by setting `DEFAULT_PAGINATION_CLASS` to `rest_framework.pagination.PageNumberPagination` and `PAGE_SIZE` to `10` so the submissions list returns the standard paginated envelope.

2. Fix the submissions queryset in `app/views.py` to use `select_related('candidate', 'assessment')` so candidate and assessment data are loaded in the same query and the list endpoint no longer suffers from N+1 queries.

3. Tighten access control in `app/views.py` by filtering `get_queryset()` based on the authenticated user: staff users get all submissions, while non-staff users only get submissions where `candidate=request.user`. This automatically protects both list and detail actions because DRF uses `get_queryset()` for object lookup.

4. Enforce one submission per candidate per assessment at the model level by adding a `UniqueConstraint` in `Submission.Meta` and creating a migration for it. This gives database-level protection against duplicates.

5. Add serializer-level validation in `app/serializers.py` that checks whether the current authenticated user already has a submission for the selected assessment and raises a clear `400` validation error on `assessment_id` before attempting creation.

6. Also guard `SubmissionSerializer.create()` with an `IntegrityError` catch so concurrent duplicate requests still return a clean validation error even if the database constraint is what prevents the duplicate.

7. Keep create behavior the same in `perform_create()` by saving the submission with `candidate=self.request.user`, preserving the response schema while ensuring candidates cannot impersonate another user.

8. Complete the access-control tests in `app/tests.py` to verify: unauthenticated requests return `401`, candidates can retrieve their own submission, candidates get `404` for other users’ submissions, staff can retrieve any submission, and a candidate list only contains their own records.

9. Complete duplicate-submission tests to verify the first POST succeeds with `201`, a second POST for the same assessment returns `400`, and only one submission exists in the database.

10. Complete pagination tests to verify the list response includes `count`, `next`, `previous`, and `results`, and that no page returns more than 10 results.

11. Complete the query-count test using `CaptureQueriesContext` so the list endpoint is asserted to stay within a bounded number of queries (5 or fewer), proving the N+1 issue is fixed.

12. Run migrations, then run the Django test suite for `app` and confirm all tests pass with the corrected access control, duplicate protection, pagination, and query efficiency.

