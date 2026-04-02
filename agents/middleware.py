class AgentReferralMiddleware:
    """Store agent referral code in session when user visits with ref link"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if there's an agent referral code in URL
        agent_code = request.GET.get('ref') or request.GET.get('agent')
        
        if agent_code:
            # Store in session (stays for 30 days)
            request.session['agent_referral'] = agent_code
            request.session.set_expiry(2592000)  # 30 days
        
        response = self.get_response(request)
        return response