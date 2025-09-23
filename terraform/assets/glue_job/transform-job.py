import sys
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue import DynamicFrame
from pyspark.sql import functions as F

def read_parquet(glueContext, path):
    return glueContext.create_dynamic_frame.from_options(
        connection_type="s3",
        connection_options={"paths": [path]},
        format="parquet"
    )

def write_parquet(glueContext, dyf, path):
    glueContext.write_dynamic_frame.from_options(
        frame=dyf,
        connection_type="s3",
        connection_options={"path": path},
        format="parquet"
    )

args = getResolvedOptions(
    sys.argv, ["JOB_NAME", "source_path", "target_path"]
)
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

source_path = args["source_path"]
target_path = args["target_path"]

# Read all tables
users = read_parquet(glueContext, f"{source_path}/users/")
posts = read_parquet(glueContext, f"{source_path}/posts/")
likes = read_parquet(glueContext, f"{source_path}/interactions/likes/")
comments = read_parquet(glueContext, f"{source_path}/interactions/comments/")
bookmarks = read_parquet(glueContext, f"{source_path}/interactions/bookmarks/")

# Convert to DataFrames for easier manipulation
users_df = users.toDF()
posts_df = posts.toDF()
likes_df = likes.toDF()
comments_df = comments.toDF()
bookmarks_df = bookmarks.toDF()

# Aggregate interactions

# Likes per user per post
likes_agg = likes_df.groupBy("user_id", "post_id").agg(F.lit(1).alias("liked"))

# Bookmarks per user per post
bookmarks_agg = bookmarks_df.groupBy("user_id", "post_id").agg(F.lit(1).alias("bookmarked"))

# Comments per user per post
comments_agg = comments_df.groupBy("user_id", "post_id") \
    .agg(
        F.count("content").alias("comments_count"),
        F.collect_list("content").alias("comments")
    )

# Start with all user-post pairs that have any interaction
user_post = likes_agg.select("user_id", "post_id") \
    .union(bookmarks_agg.select("user_id", "post_id")) \
    .union(comments_agg.select("user_id", "post_id")) \
    .dropDuplicates()

# Join all interaction types
result = user_post \
    .join(likes_agg, ["user_id", "post_id"], "left") \
    .join(bookmarks_agg, ["user_id", "post_id"], "left") \
    .join(comments_agg, ["user_id", "post_id"], "left") \
    .fillna({"liked": 0, "bookmarked": 0, "comments_count": 0, "comments": []})

# Optionally, join with user and post info
result = result \
    .join(users_df, "user_id", "left") \
    .join(posts_df, "post_id", "left")

# Convert back to DynamicFrame and write
final_dyf = DynamicFrame.fromDF(result, glueContext, "final_dyf")
write_parquet(glueContext, final_dyf, f"{target_path}/user_post_interactions/")

job.commit()