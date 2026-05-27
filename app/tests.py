from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Assessment, Submission


def make_user(username, is_staff=False):
    user = User.objects.create_user(
        username=username,
        password='testpassword123',
        is_staff=is_staff
    )
    return user


def auth_client(user):
    client = APIClient()
    token = Token.objects.get(user=user)
    client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
    return client


def submissions_list_url():
    return reverse('submission-list')


def submission_detail_url(submission_id):
    return reverse('submission-detail', args=[submission_id])


class AccessControlTests(TestCase):
    """
    Verifies that candidates can only access their own submissions
    and that unauthenticated requests are rejected.
    """

    def setUp(self):
        self.assessment = Assessment.objects.create(title='Django Basics', max_score=100)
        self.candidate_a = make_user('candidate_a')
        self.candidate_b = make_user('candidate_b')
        self.staff_user = make_user('staff_member', is_staff=True)

        self.submission_a = Submission.objects.create(
            candidate=self.candidate_a,
            assessment=self.assessment
        )
        self.submission_b = Submission.objects.create(
            candidate=self.candidate_b,
            assessment=self.assessment
        )

    def test_unauthenticated_list_is_rejected(self):
        client = APIClient()
        response = client.get(submissions_list_url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_candidate_cannot_retrieve_other_candidates_submission(self):
        client = auth_client(self.candidate_a)
        response = client.get(submission_detail_url(self.submission_b.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_candidate_can_retrieve_own_submission(self):
        client = auth_client(self.candidate_a)
        response = client.get(submission_detail_url(self.submission_a.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.submission_a.id)
        self.assertEqual(response.data['candidate']['username'], self.candidate_a.username)
        self.assertEqual(response.data['assessment']['id'], self.assessment.id)

    def test_staff_can_retrieve_any_submission(self):
        client = auth_client(self.staff_user)

        response_a = client.get(submission_detail_url(self.submission_a.id))
        response_b = client.get(submission_detail_url(self.submission_b.id))

        self.assertEqual(response_a.status_code, status.HTTP_200_OK)
        self.assertEqual(response_b.status_code, status.HTTP_200_OK)
        self.assertEqual(response_a.data['id'], self.submission_a.id)
        self.assertEqual(response_b.data['id'], self.submission_b.id)

    def test_candidate_list_only_shows_own_submissions(self):
        client = auth_client(self.candidate_a)
        response = client.get(submissions_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

        result_ids = [item['id'] for item in response.data['results']]
        self.assertEqual(result_ids, [self.submission_a.id])


class DuplicateSubmissionTests(TestCase):
    """
    Verifies that a candidate cannot submit more than once per assessment.
    """

    def setUp(self):
        self.assessment = Assessment.objects.create(title='Python ORM', max_score=100)
        self.candidate = make_user('repeat_candidate')
        self.client = auth_client(self.candidate)

    def test_first_submission_succeeds(self):
        response = self.client.post(
            submissions_list_url(),
            {'assessment_id': self.assessment.id},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Submission.objects.count(), 1)
        self.assertEqual(response.data['candidate']['username'], self.candidate.username)
        self.assertEqual(response.data['assessment']['id'], self.assessment.id)

    def test_duplicate_submission_is_rejected(self):
        first_response = self.client.post(
            submissions_list_url(),
            {'assessment_id': self.assessment.id},
            format='json'
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.client.post(
            submissions_list_url(),
            {'assessment_id': self.assessment.id},
            format='json'
        )

        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('assessment_id', second_response.data)
        self.assertEqual(Submission.objects.count(), 1)


class PaginationTests(TestCase):
    """
    Verifies that the submissions list endpoint returns paginated results.
    """

    def setUp(self):
        self.staff = make_user('paginator_staff', is_staff=True)
        self.client = auth_client(self.staff)
        self.assessment = Assessment.objects.create(title='Pagination Check', max_score=100)
        for i in range(15):
            candidate = make_user(f'page_candidate_{i}')
            Submission.objects.create(candidate=candidate, assessment=self.assessment)

    def test_list_response_is_paginated(self):
        response = self.client.get(submissions_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 15)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])

    def test_page_size_does_not_exceed_ten(self):
        first_page = self.client.get(submissions_list_url())
        second_page = self.client.get(submissions_list_url(), {'page': 2})

        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(first_page.data['results']), 10)
        self.assertLessEqual(len(second_page.data['results']), 10)


class QueryCountTests(TestCase):
    """
    Verifies that the submissions list endpoint does not produce N+1 queries.
    """

    def setUp(self):
        self.staff = make_user('query_staff', is_staff=True)
        self.client = auth_client(self.staff)
        self.assessment = Assessment.objects.create(title='Query Count Test', max_score=100)
        for i in range(10):
            candidate = make_user(f'qc_candidate_{i}')
            Submission.objects.create(candidate=candidate, assessment=self.assessment)

    def test_list_query_count_is_bounded(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(submissions_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 10)
        self.assertEqual(len(response.data['results']), 10)
        self.assertLessEqual(
            len(queries),
            5,
            msg='Expected at most 5 queries but got %s. Queries: %s' % (
                len(queries),
                [query['sql'] for query in queries.captured_queries],
            )
        )
