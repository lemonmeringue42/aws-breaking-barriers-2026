"""
Local Services Lookup Tool
Find nearby Citizens Advice bureaus and support services by postcode.
"""

import os
import logging
import requests
from strands import tool

logger = logging.getLogger(__name__)

# Postcode.io API for geocoding
POSTCODE_API = "https://api.postcodes.io/postcodes"

# Mock data - in production, this would come from Citizens Advice API
CITIZENS_ADVICE_BUREAUS = {
    "London": [
        {"name": "Citizens Advice Westminster", "phone": "020 7834 2505", "address": "70 Horseferry Road, London SW1P 2AF"},
        {"name": "Citizens Advice Camden", "phone": "020 7284 6500", "address": "2 Highgate Road, London NW5 1NR"},
        {"name": "Citizens Advice Southwark", "phone": "020 7732 2008", "address": "1 Addington Square, London SE5 7JZ"},
    ],
    "Manchester": [
        {"name": "Citizens Advice Manchester", "phone": "0161 226 5000", "address": "St James House, Pendleton Way, Manchester M6 5FX"},
    ],
    "Birmingham": [
        {"name": "Citizens Advice Birmingham", "phone": "0121 464 7930", "address": "1 Printing House Street, Birmingham B4 6DF"},
    ],
    "Scotland": [
        {"name": "Citizens Advice Scotland", "phone": "0800 028 1456", "address": "Spectrum House, 2 Powderhall Road, Edinburgh EH7 4GB"},
    ],
    "Wales": [
        {"name": "Citizens Advice Cymru", "phone": "03444 77 20 20", "address": "Ty Coch, Llanishen, Cardiff CF14 5GH"},
    ],
}

SUPPORT_SERVICES = {
    "food_banks": {
        "name": "Trussell Trust Food Bank Finder",
        "phone": "01722 580 180",
        "website": "https://www.trusselltrust.org/get-help/find-a-foodbank/",
        "description": "Find your nearest food bank"
    },
    "debt_advice": {
        "name": "StepChange Debt Charity",
        "phone": "0800 138 1111",
        "website": "https://www.stepchange.org",
        "description": "Free debt advice and solutions"
    },
    "legal_aid": {
        "name": "Civil Legal Advice",
        "phone": "0345 345 4345",
        "website": "https://www.gov.uk/civil-legal-advice",
        "description": "Free legal advice if you're eligible"
    },
    "housing": {
        "name": "Shelter Housing Advice",
        "phone": "0808 800 4444",
        "website": "https://www.shelter.org.uk",
        "description": "Emergency housing advice and support"
    },
}


@tool
def find_local_services(postcode: str, service_type: str = "citizens_advice") -> str:
    """
    Find local Citizens Advice bureaus and support services by postcode.
    
    Args:
        postcode: UK postcode (e.g., "SW1A 1AA", "M1 1AE")
        service_type: Type of service to find. Options:
            - "citizens_advice" (default): Find nearest Citizens Advice bureau
            - "food_bank": Find food banks
            - "debt_advice": Debt advice services
            - "legal_aid": Legal aid providers
            - "housing": Housing support services
            - "all": Show all available services
    
    Returns:
        Formatted information about local services
    """
    try:
        logger.info(f"🔍 Looking up services for postcode: {postcode}, type: {service_type}")
        
        # Clean postcode
        postcode = postcode.strip().upper().replace(" ", "")
        
        # Validate and get location info
        try:
            response = requests.get(f"{POSTCODE_API}/{postcode}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                region = data["result"]["region"]
                admin_district = data["result"]["admin_district"]
                latitude = data["result"]["latitude"]
                longitude = data["result"]["longitude"]
                logger.info(f"📍 Location: {admin_district}, {region}")
            else:
                return f"Invalid postcode: {postcode}. Please check and try again."
        except Exception as e:
            logger.error(f"Postcode lookup failed: {e}")
            return "Unable to validate postcode. Please check the format (e.g., SW1A 1AA) and try again."
        
        # Find Citizens Advice bureau
        if service_type == "citizens_advice" or service_type == "all":
            bureaus = _find_nearest_bureau(region, admin_district)
            
            result = f"**Citizens Advice Bureaus near {postcode}:**\n\n"
            
            for bureau in bureaus:
                result += f"📍 **{bureau['name']}**\n"
                result += f"   📞 Phone: {bureau['phone']}\n"
                result += f"   📫 Address: {bureau['address']}\n\n"
            
            result += "\n💡 **Tip:** Call ahead to check opening hours and whether you need an appointment.\n\n"
            
            if service_type == "citizens_advice":
                return result
        
        # Add other services
        if service_type != "citizens_advice":
            result = result if service_type == "all" else ""
            
            if service_type == "all":
                result += "**Other Support Services:**\n\n"
                services_to_show = SUPPORT_SERVICES.values()
            else:
                services_to_show = [SUPPORT_SERVICES.get(service_type)]
                if not services_to_show[0]:
                    return f"Unknown service type: {service_type}. Available types: citizens_advice, food_bank, debt_advice, legal_aid, housing, all"
            
            for service in services_to_show:
                if service:
                    result += f"🏢 **{service['name']}**\n"
                    result += f"   {service['description']}\n"
                    result += f"   📞 {service['phone']}\n"
                    result += f"   🌐 {service['website']}\n\n"
            
            return result
        
        return result
    
    except Exception as e:
        logger.error(f"Error in find_local_services: {e}", exc_info=True)
        return "I encountered an error looking up local services. Please try again or call our national helpline: 0800 144 8848"


def _find_nearest_bureau(region: str, district: str) -> list:
    """Find nearest Citizens Advice bureau based on region."""
    
    # Check for exact district match first
    if "London" in region or "London" in district:
        return CITIZENS_ADVICE_BUREAUS["London"][:2]  # Return 2 nearest
    
    if "Manchester" in district:
        return CITIZENS_ADVICE_BUREAUS["Manchester"]
    
    if "Birmingham" in district:
        return CITIZENS_ADVICE_BUREAUS["Birmingham"]
    
    if "Scotland" in region:
        return CITIZENS_ADVICE_BUREAUS["Scotland"]
    
    if "Wales" in region:
        return CITIZENS_ADVICE_BUREAUS["Wales"]
    
    # Default: return London as fallback (in production, use actual geolocation)
    return [{
        "name": "Citizens Advice (National)",
        "phone": "0800 144 8848",
        "address": "Contact us for your nearest bureau"
    }]
