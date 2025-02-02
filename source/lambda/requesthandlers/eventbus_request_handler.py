

######################################################################################################################
#  Copyright 2021 Amazon.com, Inc. or its affiliates. All Rights Reserved.                                           #
#                                                                                                                    #
#  Licensed under the Apache License Version 2.0 (the "License"). You may not use this file except in compliance     #
#  with the License. A copy of the License is located at                                                             #
#                                                                                                                    #
#      http://www.apache.org/licenses/                                                                               #
#                                                                                                                    #
#  or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES #
#  OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions    #
#  and limitations under the License.                                                                                #
######################################################################################################################

import os
import json
import configuration
from datetime import datetime
from util.logger import Logger
from util.dynamodb_utils import DynamoDBUtils



INF_HANDLER = "Request Handler {} : Received request {} at {}"
LOG_STREAM = "{}-{:0>4d}{:0>2d}{:0>2d}"
LOG_STREAM_PREFIX = "eventbus_request_handler"
EVENT_BUS_NAMESPACE_PREFIX = "/scheduler/do-not-delete-manually/{}"
EVENT_CREATE = "Create"
EVENT_DELETE = "Delete"

class EventBusRequestHandler:
    """
    Handles event from cloudwatch rule time
    """

    def __init__(self, event, context):

        self._context = context
        self._event = event
        self._configuration = None
        self._lambda_client = None
        self._config_table_name = os.getenv(configuration.ENV_CONFIG)

        # Setup logging
        self._is_trace_enabled = os.getenv("TRACE", False)
        logging_stream_name = "-".join([LOG_STREAM_PREFIX])
        dt = datetime.utcnow()
        logstream = LOG_STREAM.format(logging_stream_name, dt.year, dt.month, dt.day)
        self._logger = Logger(logstream=logstream, buffersize=60 if self._is_trace_enabled else 30, context=self._context,debug=self._is_trace_enabled)
        
    @staticmethod
    def is_handling_request(event):
        """
        Handler for EventBus request to update accounts.
        :return: True
        """
        return event.get("detail-type", "") == "Parameter Store Change"

    def handle_request(self):
        """
        Handles the CloudWatch Rule timer events
        :return:
        """
        try:
            self._logger.info(INF_HANDLER, self.__class__.__name__, json.dumps(self._event), datetime.now())
            detail = self._event.get("detail", None)
            if detail is not None:
                self._logger.debug(f"Details of the event {detail}")
                dynamodb_table = DynamoDBUtils.get_dynamodb_table_resource_ref(self._config_table_name)
                config_key = {"name": "scheduler", "type": "config"}
                if detail.get("operation") == EVENT_CREATE:
                    self._logger.info(f"Add account id from the config")
                    account = self._event.get("account")
                    update_account_ids_response = dynamodb_table.update_item(TableName=self._config_table_name, 
                                               Key=config_key,
                                               UpdateExpression="add remote_account_ids :a",
                                               ExpressionAttributeValues={
                                                   ':a': set({account})
                                               },ReturnValues="UPDATED_NEW")
                    self._logger.debug(f"Response from account update: {update_account_ids_response}")
                elif detail.get("operation") == EVENT_DELETE:
                    account = self._event.get("account")
                    self._logger.info(f"remove account {account} from the config")
                    update_account_ids_response = dynamodb_table.update_item(TableName=self._config_table_name, 
                                            Key=config_key,
                                            UpdateExpression="delete remote_account_ids :a",
                                            ExpressionAttributeValues={
                                                ':a': set({account})
                                            },ReturnValues="UPDATED_NEW")
                    self._logger.debug(f"Response from account update: {update_account_ids_response}")
                else:
                    self._logger.info(f"event details.operations doesn't match the scenarios configured. {detail}")
            return "Exiting event bus request handler"
        except Exception as error:
            self._logger.error(error)
            return "Error in event bus request handler."
        finally:
            self._logger.flush()