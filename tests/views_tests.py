from .base import BaseTest
from mock import Mock
import json
from warm_transfer_flask import views


class RootTest(BaseTest):

    def test_renders_all_questions(self):
        response = self.client.get('/')
        self.assertEquals(200, response.status_code)

    def test_generate_token(self):
        views.token = token_mock = Mock()
        token_mock.generate.return_value = 'token123'
        response = self.client.post('/user1/token')

        self.assertEquals(200, response.status_code)
        response_as_dict = json.loads(response.data.decode('utf8'))
        expected_dict = {'token': 'token123', 'agentId': 'user1'}
        self.assertEquals(expected_dict, response_as_dict)

        token_mock.generate.assert_called_with('user1')
