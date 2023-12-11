import grpc
import sys
import os
sys.path.insert(1, '../protos')
import reddit_pb2
import reddit_pb2_grpc
import unittest
from client import get_most_upvoted_reply_under_top_comment

class TestGetMostUpvotedReplyUnderTopComment(unittest.TestCase):
    def setUp(self):
        # Set up the gRPC channel and stub
        self.channel = grpc.insecure_channel('localhost:50051')
        self.stub = reddit_pb2_grpc.RedditServiceStub(self.channel)

        # Create a post
        self.post_response = self.stub.CreatePost(reddit_pb2.CreatePostRequest(title="Test Post", content="Content for test post"))
        self.post_id = self.post_response.post.id

        # Create a comment on the post and upvote it
        comment_response = self.stub.CreateComment(reddit_pb2.CreateCommentRequest(content="This is a test comment", postId=self.post_id, authorId="test_user"))
        self.stub.VoteComment(reddit_pb2.VoteCommentRequest(commentId=comment_response.comment.id, voteType=reddit_pb2.UPVOTE))

        # Create a reply to the comment and upvote it
        reply_response = self.stub.CreateComment(reddit_pb2.CreateCommentRequest(content="This is a test reply", commentId=comment_response.comment.id, authorId="test_user"))
        self.stub.VoteComment(reddit_pb2.VoteCommentRequest(commentId=reply_response.comment.id, voteType=reddit_pb2.UPVOTE))

    def test_get_most_upvoted_reply_under_top_comment(self):
        most_upvoted_reply = get_most_upvoted_reply_under_top_comment(self.stub, self.post_id)
        self.assertIsNotNone(most_upvoted_reply, "There should be a most upvoted reply.")
        self.assertIn("reply", most_upvoted_reply.comment.content, "The most upvoted reply should contain the word 'reply'.")

    def tearDown(self):
        self.channel.close()

if __name__ == '__main__':
    unittest.main()