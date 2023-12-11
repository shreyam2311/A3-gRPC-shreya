import grpc
import sys
import os
sys.path.insert(1, './protos')
import reddit_pb2
import reddit_pb2_grpc
import threading
import time

def get_most_upvoted_reply_under_top_comment(stub, post_id):
    # Task 1: Retrieve a post
    try:
        retrieved_post = stub.GetPost(reddit_pb2.GetPostRequest(id=post_id))
        print("Post retrieved:", retrieved_post.post.title, "-", retrieved_post.post.content)
    except grpc.RpcError as e:
        print(f"Error retrieving post: {e.code()}: {e.details()}")
        return None

    # Task 2: Retrieve the Most Upvoted Comments Under the Post
    try:
        top_comments_response = stub.GetTopComments(reddit_pb2.GetTopCommentsRequest(postId=post_id, numberOfComments=1))
        if not top_comments_response.comments:
            print("No comments found for the post.")
            return None
        most_upvoted_comment = top_comments_response.comments[0].comment
        print("Most upvoted comment:", most_upvoted_comment.content, "Score is", most_upvoted_comment.score)
    except grpc.RpcError as e:
        print(f"Error retrieving top comments: {e.code()}: {e.details()}")
        return None

    # Task 3: Expand the Most Upvoted Comment
    try:
        expanded_comment_response = stub.ExpandCommentBranch(reddit_pb2.ExpandCommentBranchRequest(parentCommentId=most_upvoted_comment.id, numberOfComments=1))
        if not expanded_comment_response.comments:
            print("No replies found for the most upvoted comment.")
            return None
        most_upvoted_reply = expanded_comment_response.comments[0].replies[0]
        print("Most upvoted reply:", most_upvoted_reply.comment.content)
    except grpc.RpcError as e:
        print(f"Error expanding comment branch: {e.code()}: {e.details()}")
        return None

    # Task 4: Return the Most Upvoted Reply Under the Most Upvoted Comment
    return most_upvoted_reply if most_upvoted_reply else None

def run(stub):
        # Create a post
        post_response = stub.CreatePost(reddit_pb2.CreatePostRequest(title="Sample Post", content="This is a sample post"))
        post_id = post_response.post.id
        print(f"Post created with ID: {post_id}")

        # Create comments on the post
        for i in range(3):
            comment_content = f"This is comment {i}"
            comment_response = stub.CreateComment(reddit_pb2.CreateCommentRequest(content=comment_content, postId=post_id, authorId="user1"))
            comment_id = comment_response.comment.id

            # Upvote the first comment
            if i == 0:
                stub.VoteComment(reddit_pb2.VoteCommentRequest(commentId=comment_id, voteType=reddit_pb2.UPVOTE))
                # Create and upvote a reply to the first comment
                for j in range(2):
                    reply_content = f"This is a reply {j} to comment {i}"
                    reply_response = stub.CreateComment(reddit_pb2.CreateCommentRequest(content=reply_content, commentId=comment_id, authorId="user2"))  
                    # Upvote the first reply
                    if j == 0:
                        stub.VoteComment(reddit_pb2.VoteCommentRequest(commentId=reply_response.comment.id, voteType=reddit_pb2.UPVOTE))
        # Use the function to get the most upvoted reply under the top comment
        most_upvoted_reply = get_most_upvoted_reply_under_top_comment(stub, post_id)
        if most_upvoted_reply:
            print("Most upvoted reply under the top comment:", most_upvoted_reply.comment.content)
        else:
            print("No upvoted replies found under the top comment.")

def monitor_updates(stub):
    def request_generator():
        # Send initial request for a post
        yield reddit_pb2.MonitorRequest(postId="1")  # Replace "1" with the actual post ID

        # Continuously check for user input to send additional requests
        while True:
            comment_id = input("Enter a comment ID to monitor (or 'exit' to stop): ")
            if comment_id.lower() == 'exit':
                break
            yield reddit_pb2.MonitorRequest(commentId=comment_id)
    def listen_for_updates():
        try:
            for update in stub.MonitorUpdates(request_generator()):
                if update.HasField('postId'):
                    print(f"Updated score for post {update.postId}: {update.score}")
                elif update.HasField('commentId'):
                    print(f"Updated score for comment {update.commentId}: {update.score}")

        except grpc.RpcError as e:
            print(f"RPC failed: {e.code()}: {e.details()}")
    # Start listening for updates in a separate thread
    listener_thread = threading.Thread(target=listen_for_updates)
    listener_thread.start()

    # Wait for the listening thread to finish (when user enters 'exit')
    listener_thread.join()

if __name__ == '__main__':
    # Establish a connection to the server
    channel = grpc.insecure_channel('localhost:50051')
    stub = reddit_pb2_grpc.RedditServiceStub(channel)

    # Run the main functionality
    run(stub)

    # Monitor updates based on user input
    monitor_updates(stub)

    # Close the channel after all operations are done
    channel.close()

