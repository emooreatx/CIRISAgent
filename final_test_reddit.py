import unittest
from unittest.mock import patch, MagicMock

from ciris_reddit_agent import CIRISRedditAgent

class TestCIRISRedditAgent(unittest.TestCase):
    @patch("ciris_reddit_agent.openai.ChatCompletion.create")
    @patch("ciris_reddit_agent.praw.Reddit")
    def test_reply_logic(self, mock_reddit, mock_openai_create):
        # Set up mock Reddit comment
        mock_comment = MagicMock()
        mock_comment.body = "What is CIRIS?"
        mock_comment.author.name = "user123"
        mock_comment.id = "abc123"
        mock_comment.reply = MagicMock()

        # Set up mock Reddit instance
        mock_subreddit = MagicMock()
        mock_subreddit.stream.comments.return_value = [mock_comment]
        mock_reddit.return_value.subreddit.return_value = mock_subreddit

        # Set up mock OpenAI response
        mock_openai_create.return_value.choices = [MagicMock(message=MagicMock(content='{"entropy": 0.01, "coherence": 0.99}'))]
        
        # Patch generate_response to avoid LLM call
        with patch.object(CIRISRedditAgent, "generate_response", return_value="This is a CIRIS-aligned reply."):
            agent = CIRISRedditAgent(mock_reddit, "testsub")
            # Patch _sense_alignment to avoid eval
            with patch.object(agent, "_sense_alignment", return_value={"entropy": 0.01, "coherence": 0.99}):
                # Patch _should_reply to always True
                with patch.object(agent, "_should_reply", return_value=True):
                    agent._reply(mock_comment)
                    mock_comment.reply.assert_called_once()
                    self.assertIn("CIRIS-aligned reply", mock_comment.reply.call_args[0][0])

if __name__ == "__main__":
    unittest.main()
