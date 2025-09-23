
resource "aws_glue_job" "extract_job" {
  name         = "${var.project}-extract-job"
  role_arn     = aws_iam_role.glue_role.arn
  glue_version = "4.0"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.scripts.id}/${aws_s3_object.glue_extract_job_script.id}"
    python_version  = 3
  }

  default_arguments = {
    "--enable-job-insights" = "true"
    "--job-language"        = "python"
    "--stage"               = var.stage
    "--target_path"         = "s3://${aws_s3_bucket.data_lake.bucket}/raw"
  }

  timeout = 5

  number_of_workers = 2
  worker_type       = "G.1X"
}



resource "aws_glue_job" "transform_job" {
  name         = "${var.project}-transform-job"
  role_arn     = aws_iam_role.glue_role.arn
  glue_version = "4.0"

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.scripts.id}/${aws_s3_object.glue_transform_job_script.id}"
    python_version  = 3
  }

  default_arguments = {
    "--enable-job-insights" = "true"
    "--job-language"        = "python"
    "--source_path"         = "s3://${aws_s3_bucket.data_lake.bucket}/raw"
    "--target_path"         = "s3://${aws_s3_bucket.data_lake.bucket}/transformed"
  }

  timeout = 5

  number_of_workers = 2
  worker_type       = "G.1X"
}



resource "aws_glue_trigger" "extract_daily" {
  name     = "${var.project}-extract-daily-trigger"
  type     = "SCHEDULED"
  schedule = "cron(0 0 * * ? *)" # Runs daily at midnight UTC

  actions {
    job_name = aws_glue_job.extract_job.name
  }

  start_on_creation = true
}

resource "aws_glue_trigger" "transform_on_extract_success" {
  name     = "${var.project}-transform-on-extract-success"
  type     = "CONDITIONAL"

  actions {
    job_name = aws_glue_job.transform_job.name
  }

  predicate {
    conditions {
      job_name = aws_glue_job.extract_job.name
      state    = "SUCCEEDED"
    }
    logical = "ANY"
  }

  start_on_creation = true
}
