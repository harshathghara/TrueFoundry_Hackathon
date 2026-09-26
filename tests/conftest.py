import os

import boto3
import pytest
from moto import mock_aws

os.environ.update(
    {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "JANITOR_REQUIRE_TAG": "janitor-demo=true",
    }
)

REGION = "us-east-1"
DEMO_TAG = {"Key": "janitor-demo", "Value": "true"}


@pytest.fixture
def aws():
    with mock_aws():
        yield


@pytest.fixture
def ec2(aws):
    return boto3.client("ec2", region_name=REGION)


@pytest.fixture
def elbv2(aws):
    return boto3.client("elbv2", region_name=REGION)


@pytest.fixture
def ami_id(ec2):
    return ec2.describe_images(Owners=["amazon"])["Images"][0]["ImageId"]


@pytest.fixture
def az(ec2):
    return ec2.describe_availability_zones()["AvailabilityZones"][0]["ZoneName"]
