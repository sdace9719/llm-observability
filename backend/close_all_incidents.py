from datetime import datetime, timedelta, timezone
import os
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.incidents_api import IncidentsApi
from datadog_api_client.v2.model.incident_update_request import IncidentUpdateRequest
from datadog_api_client.v2.model.incident_update_data import IncidentUpdateData
from datadog_api_client.v2.model.incident_update_attributes import IncidentUpdateAttributes
from datadog_api_client.v2.model.incident_type import IncidentType
from dotenv import load_dotenv

load_dotenv()

IST = timezone(timedelta(hours=5, minutes=30))

# CONFIGURATION
configuration = Configuration()
configuration.api_key['apiKeyAuth'] = os.getenv('DD_API_KEY')
configuration.api_key['appKeyAuth'] = os.getenv('DD_APP_KEY')

print(configuration.api_key['apiKeyAuth'], configuration.api_key['appKeyAuth'])

with ApiClient(configuration) as api_client:
    api_instance = IncidentsApi(api_client)
    
    # 1. List all active incidents
    # We filter for 'active' or 'stable' to avoid re-closing already resolved ones
    print("Fetching active incidents...")
    configuration.unstable_operations["search_incidents"] = True
    configuration.unstable_operations["update_incident"] = True
    with ApiClient(configuration) as api_client:
        api_instance = IncidentsApi(api_client)
        response = api_instance.search_incidents(
            query="state:active",
        )

    incidents_list = response.data.attributes.incidents

    if not incidents_list:
        print("No active incidents found.")
    
    for item in incidents_list:
        # CRITICAL: The ID is nested inside 'data' within each list item
        # Structure: item['data']['id']
        incident_id = item.data.id 
        
        print(f"Closing Incident UUID: {incident_id}")

        # 4. Update the status to RESOLVED
        body = IncidentUpdateRequest(
            data=IncidentUpdateData(
                id=incident_id,
                type=IncidentType.INCIDENTS,
                attributes=IncidentUpdateAttributes(
                    status="resolved",  # Use raw string "resolved"
                    resolved=datetime.now(IST),
                    fields={
                        "state": {
                            "type": "dropdown",
                            "value": "resolved"  # <--- Make sure this matches your dropdown option exactly!
                        }
                    }
                ),
            ),
        )

        try:
            res = api_instance.update_incident(incident_id, body)
            print(f"✅ Successfully closed {incident_id}")
            #print(res.data)
        except Exception as e:
            print(f"❌ Failed to close {incident_id}: {e}")