import sys

from awsglue import DynamicFrame
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

def sparkSqlQuery(
    glueContext, query, mapping, transformation_ctx
) -> DynamicFrame:
    for alias, frame in mapping.items():
        frame.toDF().createOrReplaceTempView(alias)
    result = spark.sql(query)
    return DynamicFrame.fromDF(result, glueContext, transformation_ctx)

def read_dynamodb_table(glueContext, table_name, splits=100, read_percent="1.0"):
    return glueContext.create_dynamic_frame.from_options(
        connection_type="dynamodb",
        connection_options={
            "dynamodb.input.tableName": table_name,
            "dynamodb.throughput.read.percent": read_percent,
            "dynamodb.splits": str(splits)
        }
    )

def write_to_s3(glueContext, dyf, path, format="parquet"):
    glueContext.write_dynamic_frame.from_options(
        frame=dyf,
        connection_type="s3",
        connection_options={"path": path},
        format=format
    )

args = getResolvedOptions(
    sys.argv, ["JOB_NAME", "stage", "target_path"]
)
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

stage = args["stage"]
target_path = args["target_path"]

# Table configs: (table_suffix, select_fields, s3_subpath)
tables = [
    ("users", ["user_id", "username", "first_name", "last_name", "bio", "dob", "location", "language", "gender"], "users/"),
    ("posts", ["post_id", "title", "file_size", "page_count", "likes_count", "comments_count"], "posts/"),
    ("follows", ["follower_id", "following_id"], "interactions/follows/"),
    ("likes", ["user_id", "post_id"], "interactions/likes/"),
    ("bookmarks", ["user_id", "post_id"], "interactions/bookmarks/"),
    ("comments", ["user_id", "post_id", "content"], "interactions/comments/"),
]

for suffix, fields, subpath in tables:
    table_name = f"docgram-{stage}-{suffix}"
    dyf = read_dynamodb_table(glueContext, table_name)
    dyf = dyf.select_fields(paths=fields)
    write_to_s3(glueContext, dyf, f"{target_path}/{subpath}")

job.commit()