# Docgram API Documentation

This documentation provides a detailed guide to using the Docgram API. It covers all the available endpoints, request and response formats, and best practices for handling edge cases.

## Authentication

Authentication is handled via JWT (JSON Web Tokens). To access protected endpoints, you need to include an `Authorization` header with the value `Bearer <your_access_token>`.

### `POST /login`

Authenticates a user and returns an access token.

**Request Body:**

The request should be a `multipart/form-data` with the following fields:

*   `username` (string, required): The user's username or email.
*   `password` (string, required): The user's password.

**Responses:**

*   **200 OK:** Successful login.

    ```json
    {
      "access_token": "your_jwt_token",
      "token_type": "bearer",
      "user": {
        "user_id": "user_uuid",
        "username": "testuser",
        "email": "user@example.com",
        "full_name": "Test User",
        "bio": "This is a bio.",
        "avatar_url": "https://example.com/avatar.jpg",
        "followers_count": 10,
        "following_count": 5,
        "posts_count": 3,
        "created_at": "2025-08-28T12:00:00Z"
      }
    }
    ```

*   **401 Unauthorized:** Incorrect username or password.

    ```json
    {
      "detail": "Incorrect username or password"
    }
    ```

*   **400 Bad Request:** The user account is inactive.

    ```json
    {
      "detail": "Inactive user"
    }
    ```

*   **500 Internal Server Error:** An unexpected error occurred.

**Edge Cases & Best Practices:**

*   Store the `access_token` securely on the client-side (e.g., in an HttpOnly cookie or secure storage).
*   The token has an expiration time. Your application should handle token expiration and renewal.
*   Implement rate limiting to prevent brute-force attacks.

### `POST /register`

Registers a new user.

**Request Body:**

*   `username` (string, required): A unique username (3-30 characters).
*   `email` (string, required): A unique email address.
*   `password` (string, required): A password (min 6 characters).
*   `first_name` (string, optional): The user's first name (max 30 characters).
*   `last_name` (string, optional): The user's last name (max 30 characters).
*   `bio` (string, optional): A short bio (max 500 characters).

**Responses:**

*   **200 OK:** Successful registration. The response body is the same as the `/login` endpoint.

*   **400 Bad Request:**
    *   If the username is already registered: `{"detail": "Username already registered"}`
    *   If the email is already registered: `{"detail": "Email already registered"}`

*   **500 Internal Server Error:** An unexpected error occurred.

**Edge Cases & Best Practices:**

*   Provide clear feedback to the user if their chosen username or email is already taken.
*   After successful registration, you can automatically log the user in.

## Users

Endpoints for managing user profiles and relationships.

### `GET /users/me`

Retrieves the profile of the currently authenticated user.

**Request:**

*   Requires authentication.

**Responses:**

*   **200 OK:**

    ```json
    {
      "user_id": "user_uuid",
      "username": "testuser",
      "email": "user@example.com",
      "full_name": "Test User",
      "bio": "This is a bio.",
      "avatar_url": "https://example.com/avatar.jpg",
      "followers_count": 10,
      "following_count": 5,
      "posts_count": 3,
      "created_at": "2025-08-28T12:00:00Z"
    }
    ```

*   **401 Unauthorized:** If the user is not authenticated.

### `PUT /users/profile`

Updates the profile of the currently authenticated user.

**Request:**

*   Requires authentication.
*   The request can be a `multipart/form-data` if an avatar is being uploaded, or `application/json` for other fields.

**Request Body:**

*   `username` (string, optional): A new unique username (3-30 characters).
*   `email` (string, optional): A new unique email.
*   `first_name` (string, optional): New first name (max 30 characters).
*   `last_name` (string, optional): New last name (max 30 characters).
*   `bio` (string, optional): New bio (max 500 characters).
*   `avatar_file` (file, optional): An image file for the avatar (JPG, JPEG, PNG, max 5MB).

**Responses:**

*   **200 OK:** Profile updated successfully. The response body contains the updated user profile.

*   **400 Bad Request:**
    *   If the username is already taken: `{"detail": "Username already taken"}`
    *   If the email is already taken: `{"detail": "Email already taken"}`
    *   Invalid file type or size for the avatar.

*   **401 Unauthorized:** Not authenticated.
*   **500 Internal Server Error:** An unexpected error occurred.

**Edge Cases & Best Practices:**

*   Allow users to update only the fields they want to change.
*   Provide immediate feedback on the success or failure of the update.

### `POST /users/{user_id}/follow`

Follows or unfollows a user.

**Request:**

*   Requires authentication.
*   `user_id` (path parameter, string, required): The ID of the user to follow/unfollow.

**Responses:**

*   **200 OK:**

    ```json
    {
      "following": true, // or false if unfollowed
      "followers_count": 11,
      "following_count": 5
    }
    ```

*   **400 Bad Request:** If a user tries to follow themselves: `{"detail": "Cannot follow yourself"}`
*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the user with `user_id` does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `GET /users/{user_id}/profile`

Retrieves the profile of a specific user, including their posts.

**Request:**

*   Requires authentication.
*   `user_id` (path parameter, string, required): The ID of the user.

**Responses:**

*   **200 OK:**

    ```json
    {
      "profile_user": {
        "user_id": "user_uuid",
        "username": "otheruser",
        "full_name": "Other User",
        "bio": "Another bio.",
        "avatar_url": "https://example.com/other_avatar.jpg",
        "followers_count": 15,
        "following_count": 8,
        "posts_count": 5,
        "is_following": true, // if the current user is following this user
        "created_at": "2025-08-27T10:00:00Z"
      },
      "posts": [ /* list of post objects */ ],
      "total_posts": 5,
      "total_followers": 15,
      "total_following": 8
    }
    ```

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the user with `user_id` does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `GET /users/{user_id}/followers`

Retrieves the list of followers for a specific user.

**Request:**

*   Requires authentication.
*   `user_id` (path parameter, string, required): The ID of the user.
*   `offset` (query parameter, integer, optional, default: 0): The number of followers to skip.
*   `limit` (query parameter, integer, optional, default: 20, max: 100): The maximum number of followers to return.

**Responses:**

*   **200 OK:** A list of user objects.

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the user with `user_id` does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `GET /users/{user_id}/following`

Retrieves the list of users that a specific user is following.

**Request:**

*   Requires authentication.
*   `user_id` (path parameter, string, required): The ID of the user.
*   `offset` (query parameter, integer, optional, default: 0): The number of users to skip.
*   `limit` (query parameter, integer, optional, default: 20, max: 100): The maximum number of users to return.

**Responses:**

*   **200 OK:** A list of user objects.

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the user with `user_id` does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

## Posts

Endpoints for managing posts (PDFs).

### `GET /posts`

Lists public posts with pagination.

**Request:**

*   Requires authentication.
*   `offset` (query parameter, integer, optional, default: 0): The number of posts to skip.
*   `limit` (query parameter, integer, optional, default: 10, max: 50): The maximum number of posts to return.

**Responses:**

*   **200 OK:** A list of post objects.

*   **401 Unauthorized:** Not authenticated.
*   **500 Internal Server Error:** An unexpected error occurred.

### `POST /posts`

Creates a new PDF post.

**Request:**

*   Requires authentication.
*   The request must be `multipart/form-data`.

**Request Body:**

*   `pdf_file` (file, required): The PDF file to upload (max 50MB).
*   `title` (string, optional): The title of the post. If not provided, it will be generated from the filename.
*   `description` (string, optional): A description of the post.
*   `is_public` (boolean, optional, default: true): Whether the post is public or private.

**Responses:**

*   **200 OK:** The created post object.

*   **400 Bad Request:**
    *   If the file is not a PDF: `{"detail": "Only PDF files are allowed"}`
    *   If the file size exceeds the limit: `{"detail": "File size too large (max 50MB)"}`

*   **401 Unauthorized:** Not authenticated.
*   **500 Internal Server Error:** An unexpected error occurred.

**Edge Cases & Best Practices:**

*   This endpoint performs background processing for PDF embeddings. The response is returned immediately, but the embeddings might take some time to be ready for the chat feature.
*   Provide feedback to the user about the upload progress.

### `GET /posts/feed`

Retrieves a personalized feed of posts from users that the current user follows.

**Request:**

*   Requires authentication.
*   `offset` (query parameter, integer, optional, default: 0): The number of posts to skip.
*   `limit` (query parameter, integer, optional, default: 10, max: 50): The maximum number of posts to return.

**Responses:**

*   **200 OK:** A list of post objects. If the user is not following anyone, it returns public posts.

*   **401 Unauthorized:** Not authenticated.
*   **500 Internal Server Error:** An unexpected error occurred.

### `GET /posts/search`

Searches for posts by title.

**Request:**

*   Requires authentication.
*   `q` (query parameter, string, required): The search query (min 1 character).
*   `offset` (query parameter, integer, optional, default: 0): The number of posts to skip.
*   `limit` (query parameter, integer, optional, default: 10, max: 50): The maximum number of posts to return.

**Responses:**

*   **200 OK:** A list of post objects matching the search query.

*   **401 Unauthorized:** Not authenticated.
*   **500 Internal Server Error:** An unexpected error occurred.

### `GET /posts/{post_id}`

Retrieves the details of a single post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post.

**Responses:**

*   **200 OK:** The post object.

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the post with `post_id` does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `PUT /posts/{post_id}`

Updates a post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post to update.

**Request Body:**

*   `title` (string, optional): The new title.
*   `description` (string, optional): The new description.
*   `is_public` (boolean, optional): The new visibility status.

**Responses:**

*   **200 OK:** The updated post object.

*   **401 Unauthorized:** Not authenticated.
*   **403 Forbidden:** If the user is not the owner of the post.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `DELETE /posts/{post_id}`

Deletes a post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post to delete.

**Responses:**

*   **200 OK:** `{"message": "Post deleted successfully"}`

*   **401 Unauthorized:** Not authenticated.
*   **403 Forbidden:** If the user is not the owner of the post.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `PATCH /posts/{post_id}/visibility`

Toggles the public/private visibility of a post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post.

**Responses:**

*   **200 OK:** `{"is_public": true}` or `{"is_public": false}`

*   **401 Unauthorized:** Not authenticated.
*   **403 Forbidden:** If the user is not the owner of the post.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `POST /posts/{post_id}/like`

Toggles a like on a post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post.

**Responses:**

*   **200 OK:**

    ```json
    {
      "is_liked": true, // or false if unliked
      "likes_count": 25
    }
    ```

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `GET /posts/{post_id}/comments`

Retrieves the comments for a post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post.
*   `offset` (query parameter, integer, optional, default: 0): The number of comments to skip.
*   `limit` (query parameter, integer, optional, default: 20, max: 100): The maximum number of comments to return.

**Responses:**

*   **200 OK:** A list of comment objects.

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `POST /posts/{post_id}/comments`

Adds a comment to a post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post.
*   The request should be `multipart/form-data`.

**Request Body:**

*   `content` (string, required): The content of the comment (1-1000 characters).

**Responses:**

*   **200 OK:** The created comment object.

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `GET /posts/{post_id}/messages`

Retrieves the chat messages for a post.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post.

**Responses:**

*   **200 OK:** A list of chat message objects.

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

### `POST /posts/{post_id}/messages`

Sends a chat message to a post's chat. This is used for the "chat with PDF" feature.

**Request:**

*   Requires authentication.
*   `post_id` (path parameter, string, required): The ID of the post.

**Request Body:**

*   `query` (string, required): The user's message or question (1-1000 characters).

**Responses:**

*   **200 OK:** The user's message object. The assistant's response is generated in the background.

*   **401 Unauthorized:** Not authenticated.
*   **404 Not Found:** If the post does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.

**Edge Cases & Best Practices:**

*   The assistant's response is not returned immediately. You should implement a mechanism (e.g., WebSockets or polling) to receive the assistant's message once it's ready. The initial response for the assistant will be "Thinking...".

### `DELETE /posts/messages/{message_id}`

Deletes a chat message.

**Request:**

*   Requires authentication.
*   `message_id` (path parameter, string, required): The ID of the message to delete.

**Responses:**

*   **200 OK:** `{"message": "Message deleted successfully"}`

*   **401 Unauthorized:** Not authenticated.
*   **403 Forbidden:** If the user is not the owner of the conversation.
*   **404 Not Found:** If the message does not exist.
*   **500 Internal Server Error:** An unexpected error occurred.
