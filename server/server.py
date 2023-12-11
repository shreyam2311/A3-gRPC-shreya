import grpc
from concurrent import futures
import sys
import os
sys.path.insert(1, './protos')
import reddit_pb2
import reddit_pb2_grpc
from google.protobuf import timestamp_pb2
import datetime
import argparse

class RedditService(reddit_pb2_grpc.RedditServiceServicer):

    def __init__(self):
        self.users = {}
        self.posts = {}
        self.comments = {}

    def CreateUser(self, request, context):
        if request.id in self.users:
            context.abort(grpc.StatusCode.ALREADY_EXISTS, "User already exists")

        user = reddit_pb2.User(id=request.id, username=request.username, email=request.email)
        self.users[user.id] = user
        return reddit_pb2.UserResponse(user=user)

    def GetUser(self, request, context):
        user = self.users.get(request.id)
        if user:
            return reddit_pb2.UserResponse(user=user)
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "User not found")
    
    def CreatePost(self, request, context):
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%dT%H:%M")
        try:
            # print(request)
            if request.image_url and request.video_url:                
                raise ValueError("There can't be two medias in the request")
            if request.image_url == "":
                post = reddit_pb2.Post(id=str(len(self.posts) + 1), title=request.title, content=request.content, score=0, state=reddit_pb2.NORMAL, publicationDate=formatted_time, video_url=request.video_url, subredditId=request.subredditId)
            else:
                post = reddit_pb2.Post(id=str(len(self.posts) + 1), title=request.title, content=request.content, score=0, state=reddit_pb2.NORMAL, publicationDate=formatted_time, image_url=request.image_url, subredditId=request.subredditId)

            self.posts[post.id] = post
            return reddit_pb2.PostResponse(success=True, message="Post created successfully!", post=post)
        except ValueError as e:
            return reddit_pb2.PostResponse(success=False, message=str(e), post=None)


    def GetPost(self, request, context):
        post = self.posts.get(request.id)
        if post:
            return reddit_pb2.GetPostResponse(success=True,message="Post fetched successfully!",post=post)
        else:
            return reddit_pb2.GetPostResponse(success=False,message="Post not found!",post=None)

    def ListPosts(self, request, context):
        for post_id, post in self.posts.items():
            yield reddit_pb2.PostResponse(post=post)

    def CreateComment(self, request, context):
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%dT%H:%M")
        # If the comment is under a post or another comment
        root_id = request.postId if request.HasField('postId') else request.commentId
        # Validate if the root (post or comment) exists
        if root_id not in (self.posts if request.HasField('postId') else self.comments):
            return reddit_pb2.CreateCommentResponse(success=False, message="Root not found", comment=None)
        # Create a new comment
        comment = reddit_pb2.Comment(
            id=str(len(self.comments) + 1),
            content=request.content,
            postId=request.postId if request.HasField('postId') else None,
            commentId=request.commentId if request.HasField('commentId') else None,
            authorId=request.authorId,
            score=0,
            state=request.state,
            publicationDate=formatted_time
        )
        # Store the comment
        self.comments[comment.id] = comment
        # Return the response
        return reddit_pb2.CreateCommentResponse(success=True, message="Comment created successfully", comment=comment)

    def GetComment(self, request, context):
        comment = self.comments.get(request.id)
        if comment:
            return reddit_pb2.CommentResponse(comment=comment)
        else:
            context.abort(grpc.StatusCode.NOT_FOUND, "Comment not found")

    

    def ListComments(self, request, context):
        for comment_id, comment in self.comments.items():
            if comment.postId == request.postId:
                yield reddit_pb2.CommentResponse(comment=comment)

    def VotePost(self, request, context):
        # Check if the post exists
        if request.postId not in self.posts:
            return reddit_pb2.VotePostResponse(success=False, message="Post not found!", updatedScore=None)

        # Retrieve the post
        post = self.posts[request.postId]

        # Update the score based on the vote type
        if request.voteType == reddit_pb2.VoteType.UPVOTE:
            post.score += 1
        elif request.voteType == reddit_pb2.VoteType.DOWNVOTE:
            post.score -= 1

        self.posts[request.postId] = post

        return reddit_pb2.VotePostResponse(success=True, message="Score updated for the post!",updatedScore=post.score)

    def VoteComment(self, request, context):
        # Check if the post exists
        if request.commentId not in self.comments:
            return reddit_pb2.VoteCommentResponse(success=False, message="Comment not found!", updatedScore=None)

        # Retrieve the post
        comment = self.comments[request.commentId]

        # Update the score based on the vote type
        if request.voteType == reddit_pb2.VoteType.UPVOTE:
            comment.score += 1
        elif request.voteType == reddit_pb2.VoteType.DOWNVOTE:
            comment.score -= 1

        self.comments[request.commentId] = comment

        return reddit_pb2.VotePostResponse(success=True, message="Score updated for the comment!",updatedScore=comment.score)

    def GetTopComments(self, request, context):
        # Check if the post exists
        if request.postId not in self.posts:
            return reddit_pb2.GetTopCommentsResponse(success=False, message="Post not found!", comments=None)

        # Filter and sort comments for the given post
        comments_for_post = [comment for comment_id, comment in self.comments.items() if comment.postId == request.postId]
        sorted_comments = sorted(comments_for_post, key=lambda c: c.score, reverse=True)

        # Prepare the response
        response_comments = []
        for comment in sorted_comments[:request.numberOfComments]:
            # Fetch replies for each comment
            replies = [c for c_id, c in self.comments.items() if c.commentId == comment.id]
            response_comments.append(reddit_pb2.CommentWithReplies(comment=comment, replies=replies))

        # Return the response
        return reddit_pb2.GetTopCommentsResponse(success=True, message="Top comments fetched successfully!",comments=response_comments)
    
    def fetch_comments(self, comment_id, level, numberOfComments):
        if level > 2:
            return None
        comment = self.comments.get(comment_id)
        if comment:
            # Fetch all replies and sort them by score in descending order
            all_replies = [self.comments[reply_id] for reply_id in self.comments if self.comments[reply_id].commentId == comment_id]
            sorted_replies = sorted(all_replies, key=lambda x: x.score, reverse=True)

            # Fetch the top N replies based on numberOfComments
            top_replies = sorted_replies[:numberOfComments]

            # CommentTree for each valid reply
            replies = []
            for reply in top_replies:
                nested_reply_tree = self.fetch_comments(reply.id, level + 1, numberOfComments)
                if nested_reply_tree:
                    replies.append(nested_reply_tree)

            # CommentTree object for the current comment
            comment_tree = reddit_pb2.CommentTree(comment=comment, replies=replies)
            return comment_tree
        return None

    def ExpandCommentBranch(self, request, context):
        parent_comment_tree = self.fetch_comments(request.parentCommentId, 1, request.numberOfComments)

        if not parent_comment_tree:
            context.abort(grpc.StatusCode.NOT_FOUND, "No comments found")

        return reddit_pb2.ExpandCommentBranchResponse(
            success=True,
            message="Comment branch expanded",
            comments=[parent_comment_tree]
        )
# Command line argument for port, else default      
def serve(port=50051, max_workers=10):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    reddit_pb2_grpc.add_RedditServiceServicer_to_server(RedditService(), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    print(f"Server started on port {port}")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Reddit gRPC Server")
    parser.add_argument('--port', type=int, default=50051, help="Port to listen on")
    parser.add_argument('--workers', type=int, default=10, help="Number of server workers")
    args = parser.parse_args()

    serve(port=args.port, max_workers=args.workers)
