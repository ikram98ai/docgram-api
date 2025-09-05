# Docgram API Documentation

This documentation provides a detailed guide to using the Docgram API. It covers all the available endpoints, request and response formats, and best practices for handling edge cases.


## Authentication API Documentation (`app/routers/auth.py`)

Authentication is handled via JWT (JSON Web Tokens). To access protected endpoints, you need to include an `Authorization` header with the value `Bearer <your_access_token>`.

### 1. Login User
- **Endpoint:** `POST /login`
- **Description:** Authenticates a user and returns a JWT token.
- **Request Body:**
  ```json
  {
    "username": "your_username_or_email",
    "password": "your_password"
  }
  ```
- **Responses:**
  - **200 OK:** Successful login.
    ```json
    {
      "access_token": "your_jwt_token",
      "token_type": "bearer",
      "user": {
        "user_id": "user_uuid",
        "username": "string",
        "email": "user@example.com",
        "full_name": "string",
        "bio": "string",
        "avatar_url": "string",
        "followers_count": 0,
        "following_count": 0,
        "posts_count": 0,
        "created_at": "2025-09-06T12:00:00Z"
      }
    }
    ```
  - **401 Unauthorized:** Incorrect username or password.
  - **400 Bad Request:** Inactive user.
  - **500 Internal Server Error:** Login failed due to a server error.

### 2. Register User
- **Endpoint:** `POST /register/`
- **Description:** Registers a new user.
- **Request Body:**
  ```json
  {
    "username": "new_username",
    "email": "new_user@example.com",
    "password": "new_password",
    "first_name": "string",
    "last_name": "string",
    "bio": "string"
  }
  ```
- **Responses:**
  - **200 OK:** Successful registration. Returns the same response as login.
  - **400 Bad Request:** Username or email already registered.
  - **500 Internal Server Error:** Registration failed due to a server error.

## Chat API Documentation (`app/routers/chat.py`)

### 1. Delete a chat message
- **Endpoint:** `DELETE /posts/messages/{message_id}`
- **Description:** Deletes a specific chat message.
- **Request Body:** None.
- **Responses:**
  - **200 OK:**
    ```json
    {
      "message": "Message deleted successfully"
    }
    ```
  - **403 Forbidden:** The current user is not authorized to delete the message.
  - **404 Not Found:** The message with the given `message_id` was not found.
  - **500 Internal Server Error:** An error occurred while deleting the message.

### 2. Get chat messages for a post
- **Endpoint:** `GET /posts/{post_id}/messages`
- **Description:** Retrieves all chat messages associated with a specific post for the current user.
- **Request Body:** None.
- **Responses:**
  - **200 OK:**
    ```json
    [
      {
        "message_id": "string",
        "conversation_id": "string",
        "role": "user",
        "content": "string",
        "timestamp": "2025-09-06T12:00:00Z"
      }
    ]
    ```
  - **500 Internal Server Error:** An error occurred while fetching the messages.

### 3. Post a message to a chat
- **Endpoint:** `POST /posts/{post_id}/messages`
- **Description:** Sends a new message to the chat associated with a post.
- **Request Body:**
  ```json
  {
    "query": "Your message here"
  }
  ```
- **Responses:**
  - **200 OK:** A streaming response of plain text.
  - **500 Internal Server Error:** An error occurred while posting the message.

## Posts API Documentation (`app/routers/post.py`)

### 1. List public posts
- **Endpoint:** `GET /posts/`
- **Description:** Retrieves a paginated list of public posts.
- **Query Parameters:**
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 10, max: 50)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of post objects.
    ```json
    [
      {
        "id": "string",
        "user_id": "string",
        "user": {
          "user_id": "user_uuid",
          "username": "string",
          "email": "user@example.com",
          "full_name": "string",
          "bio": "string",
          "avatar_url": "string",
          "followers_count": 0,
          "following_count": 0,
          "posts_count": 0,
          "created_at": "2025-09-06T12:00:00Z"
        },
        "title": "string",
        "description": "string",
        "pdf_url": "string",
        "thumbnail_url": "string",
        "file_size": 0,
        "page_count": 0,
        "likes_count": 0,
        "comments_count": 0,
        "shares_count": 0,
        "is_liked": false,
        "is_bookmarked": false,
        "created_at": "2025-09-06T12:00:00Z",
        "is_public": true
      }
    ]
    ```
  - **500 Internal Server Error:** An error occurred while fetching the posts.

### 2. Get user feed
- **Endpoint:** `GET /posts/feed`
- **Description:** Retrieves a personalized feed of posts from users that the current user follows.
- **Query Parameters:**
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 10, max: 50)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of post objects.
    ```json
    [
      {
        "id": "string",
        "user_id": "string",
        "user": {
          "user_id": "user_uuid",
          "username": "string",
          "email": "user@example.com",
          "full_name": "string",
          "bio": "string",
          "avatar_url": "string",
          "followers_count": 0,
          "following_count": 0,
          "posts_count": 0,
          "created_at": "2025-09-06T12:00:00Z"
        },
        "title": "string",
        "description": "string",
        "pdf_url": "string",
        "thumbnail_url": "string",
        "file_size": 0,
        "page_count": 0,
        "likes_count": 0,
        "comments_count": 0,
        "shares_count": 0,
        "is_liked": false,
        "is_bookmarked": false,
        "created_at": "2025-09-06T12:00:00Z",
        "is_public": true
      }
    ]
    ```
  - **500 Internal Server Error:** An error occurred while fetching the feed.

### 3. Search posts
- **Endpoint:** `GET /posts/search`
- **Description:** Searches for posts based on a query string.
- **Query Parameters:**
  - `q`: `string` (required)
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 20, max: 50)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of post objects.
    ```json
    [
      {
        "id": "string",
        "user_id": "string",
        "user": {
          "user_id": "user_uuid",
          "username": "string",
          "email": "user@example.com",
          "full_name": "string",
          "bio": "string",
          "avatar_url": "string",
          "followers_count": 0,
          "following_count": 0,
          "posts_count": 0,
          "created_at": "2025-09-06T12:00:00Z"
        },
        "title": "string",
        "description": "string",
        "pdf_url": "string",
        "thumbnail_url": "string",
        "file_size": 0,
        "page_count": 0,
        "likes_count": 0,
        "comments_count": 0,
        "shares_count": 0,
        "is_liked": false,
        "is_bookmarked": false,
        "created_at": "2025-09-06T12:00:00Z",
        "is_public": true
      }
    ]
    ```
  - **500 Internal Server Error:** An error occurred during the search.

### 4. Create a new post
- **Endpoint:** `POST /posts/`
- **Description:** Creates a new post by uploading a PDF file.
- **Request Body:** `multipart/form-data`
  - `pdf_file`: The PDF file to upload.
  - `title`: `string` (optional)
  - `description`: `string` (optional)
  - `is_public`: `boolean` (default: `true`)
- **Responses:**
  - **200 OK:**
    ```json
    {
      "message": "Post creation is in progress. You will be notified shortly."
    }
    ```
  - **400 Bad Request:** Invalid file type or size.
  - **500 Internal Server Error:** An error occurred while creating the post.

### 5. Get post details
- **Endpoint:** `GET /posts/{post_id}`
- **Description:** Retrieves the details of a specific post.
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A post object.
  - **500 Internal Server Error:** An error occurred while fetching the post.

### 6. Update a post
- **Endpoint:** `PUT /posts/{post_id}`
- **Description:** Updates the details of a specific post.
- **Request Body:**
  ```json
  {
    "title": "string",
    "description": "string",
    "is_public": true
  }
  ```
- **Responses:**
  - **200 OK:** The updated post object.
  - **403 Forbidden:** The current user is not authorized to update the post.
  - **500 Internal Server Error:** An error occurred while updating the post.

### 7. Delete a post
- **Endpoint:** `DELETE /posts/{post_id}`
- **Description:** Deletes a specific post.
- **Request Body:** None.
- **Responses:**
  - **200 OK:**
    ```json
    {
      "message": "Post deleted successfully"
    }
    ```
  - **403 Forbidden:** The current user is not authorized to delete the post.
  - **500 Internal Server Error:** An error occurred while deleting the post.

### 8. Get post comments
- **Endpoint:** `GET /posts/{post_id}/comments`
- **Description:** Retrieves the comments for a specific post.
- **Query Parameters:**
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 20, max: 100)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of comment objects.
    ```json
    [
      {
        "comment_id": "string",
        "post_id": "string",
        "user_id": "string",
        "user": {
          "user_id": "user_uuid",
          "username": "string",
          "email": "user@example.com",
          "full_name": "string",
          "bio": "string",
          "avatar_url": "string",
          "followers_count": 0,
          "following_count": 0,
          "posts_count": 0,
          "created_at": "2025-09-06T12:00:00Z"
        },
        "content": "string",
        "created_at": "2025-09-06T12:00:00Z"
      }
    ]
    ```
  - **500 Internal Server Error:** An error occurred while fetching the comments.

### 9. Create a comment
- **Endpoint:** `POST /posts/{post_id}/comments`
- **Description:** Adds a new comment to a specific post.
- **Request Body:** `application/x-www-form-urlencoded`
  - `content`: `string` (required, min_length: 1, max_length: 1000)
- **Responses:**
  - **200 OK:** The newly created comment object.
  - **500 Internal Server Error:** An error occurred while creating the comment.

## Toggles API Documentation (`app/routers/toggles.py`)

### 1. Toggle follow
- **Endpoint:** `POST /users/{user_id}/follow`
- **Description:** Follows or unfollows a user.
- **Request Body:** None.
- **Responses:**
  - **200 OK:**
    ```json
    {
      "following": true,
      "followers_count": 0,
      "following_count": 0
    }
    ```
  - **400 Bad Request:** The user cannot follow themselves.
  - **500 Internal Server Error:** An error occurred.

### 2. Toggle like
- **Endpoint:** `POST /posts/{post_id}/like`
- **Description:** Likes or unlikes a post.
- **Request Body:** None.
- **Responses:**
  - **200 OK:**
    ```json
    {
      "is_liked": true,
      "likes_count": 0
    }
    ```
  - **500 Internal Server Error:** An error occurred.

### 3. Toggle bookmark
- **Endpoint:** `POST /posts/{post_id}/bookmark`
- **Description:** Bookmarks or unbookmarks a post.
- **Request Body:** None.
- **Responses:**
  - **200 OK:**
    ```json
    {
      "is_bookmarked": true
    }
    ```
  - **500 Internal Server Error:** An error occurred.

### 4. Toggle post visibility
- **Endpoint:** `PATCH /posts/{post_id}/visibility`
- **Description:** Toggles a post's visibility between public and private.
- **Request Body:** None.
- **Responses:**
  - **200 OK:**
    ```json
    {
      "is_public": true
    }
    ```
  - **403 Forbidden:** The current user is not authorized to change the visibility.
  - **500 Internal Server Error:** An error occurred.

## Users API Documentation (`app/routers/user.py`)

### 1. Get current user info
- **Endpoint:** `GET /users/me`
- **Description:** Retrieves the profile information of the currently authenticated user.
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A user object.
    ```json
    {
      "user_id": "string",
      "username": "string",
      "email": "user@example.com",
      "full_name": "string",
      "bio": "string",
      "avatar_url": "string",
      "followers_count": 0,
      "following_count": 0,
      "posts_count": 0,
      "created_at": "2025-09-06T12:00:00Z"
    }
    ```

### 2. Update user profile
- **Endpoint:** `PUT /users/profile`
- **Description:** Updates the profile of the currently authenticated user.
- **Request Body:** `multipart/form-data`
  - `update_data`: A JSON string with the fields to update.
    ```json
    {
      "username": "string",
      "email": "user@example.com",
      "first_name": "string",
      "last_name": "string",
      "bio": "string"
    }
    ```
  - `avatar_file`: An image file (JPG, JPEG, PNG).
- **Responses:**
  - **200 OK:** The updated user object.
  - **400 Bad Request:** Invalid file type/size or username/email already taken.
  - **500 Internal Server Error:** An error occurred.

### 3. Get user profile
- **Endpoint:** `GET /users/{user_id}/profile`
- **Description:** Retrieves the profile information of a specific user.
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A user object with an additional `is_following` field.
  - **500 Internal Server Error:** An error occurred.

### 4. Get user followers
- **Endpoint:** `GET /users/{user_id}/followers`
- **Description:** Retrieves a list of users who are following a specific user.
- **Query Parameters:**
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 20, max: 100)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of user objects.
    ```json
    [
      {
        "user_id": "user_uuid",
        "username": "string",
        "email": "user@example.com",
        "full_name": "string",
        "bio": "string",
        "avatar_url": "string",
        "followers_count": 0,
        "following_count": 0,
        "posts_count": 0,
        "created_at": "2025-09-06T12:00:00Z"
      }
    ]
    ```
  - **500 Internal Server Error:** An error occurred.

### 5. Get user following
- **Endpoint:** `GET /users/{user_id}/following`
- **Description:** Retrieves a list of users that a specific user is following.
- **Query Parameters:**
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 20, max: 100)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of user objects.
  - **500 Internal Server Error:** An error occurred.

### 6. Get user posts
- **Endpoint:** `GET /users/{user_id}/posts`
- **Description:** Retrieves a list of posts created by a specific user.
- **Query Parameters:**
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 10, max: 50)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of post objects.
  - **500 Internal Server Error:** An error occurred.

### 7. Get user bookmarks
- **Endpoint:** `GET /users/{user_id}/bookmarks`
- **Description:** Retrieves a list of posts bookmarked by the current user.
- **Query Parameters:**
  - `offset`: `integer` (default: 0)
  - `limit`: `integer` (default: 20, max: 100)
- **Request Body:** None.
- **Responses:**
  - **200 OK:** A list of post objects.
  - **403 Forbidden:** Users can only view their own bookmarks.
  - **500 Internal Server Error:** An error occurred.
