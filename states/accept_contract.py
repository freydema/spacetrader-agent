"""
ACCEPT_CONTRACT state implementation.

This state accepts a previously selected contract and prepares for execution.
"""

from typing import Optional
from models.state_enums import AgentState
from states.base_state import BaseState


class AcceptContractState(BaseState):
    """
    State for accepting a selected contract.
    
    This state:
    1. Accepts the contract that was selected in NEGOTIATE_CONTRACT
    2. Updates the contract status in the context
    3. Records acceptance metrics
    4. Prepares for contract execution
    """
    
    def execute(self) -> Optional[AgentState]:
        """
        Execute the ACCEPT_CONTRACT state logic.
        
        Returns:
            AgentState: Next state to transition to (PLAN_FULFILLMENT, NEGOTIATE_CONTRACT, or ERROR_RECOVERY)
        """
        self.log_state_entry()
        
        try:
            # Verify we have a contract to accept
            if not self.context.current_contract:
                self.logger.warning("No contract selected for acceptance - returning to negotiation")
                return AgentState.NEGOTIATE_CONTRACT
            
            contract = self.context.current_contract
            
            # Check if contract is already accepted
            if contract.accepted:
                self.logger.info(f"Contract {contract.contract_id} already accepted - proceeding to fulfillment")
                next_state = AgentState.PLAN_FULFILLMENT
                self.log_state_exit(next_state)
                return next_state
            
            # Attempt to accept the contract
            success = self._accept_contract(contract)
            
            if success:
                self.logger.info(f"Successfully accepted contract {contract.contract_id}")
                
                # Update contract status
                contract.accepted = True
                
                # Record metrics
                self._record_contract_acceptance()
                
                # Log acceptance details
                self._log_acceptance_details(contract)
                
                next_state = AgentState.PLAN_FULFILLMENT
                self.log_state_exit(next_state)
                return next_state
                
            else:
                self.logger.warning(f"Failed to accept contract {contract.contract_id} - returning to negotiation")
                # Clear the failed contract
                self.context.current_contract = None
                return AgentState.NEGOTIATE_CONTRACT
                
        except Exception as e:
            self.logger.error(f"Error in ACCEPT_CONTRACT state: {e}")
            return AgentState.ERROR_RECOVERY
    
    def _accept_contract(self, contract) -> bool:
        """
        Accept the contract via the API.
        
        Args:
            contract: Contract to accept
            
        Returns:
            bool: True if acceptance successful, False otherwise
        """
        self.logger.info(f"Attempting to accept contract {contract.contract_id}...")
        
        try:
            response = self.api_client.accept_contract(contract.contract_id)
            
            if response and 'data' in response:
                contract_data = response['data']['contract']
                agent_data = response['data']['agent']
                
                # Update contract with latest data
                if contract_data:
                    contract.accepted = contract_data.get('accepted', False)
                    contract.fulfilled = contract_data.get('fulfilled', False)
                
                # Update agent credits from the acceptance payment
                if agent_data:
                    old_credits = self.context.agent_data.credits if self.context.agent_data else 0
                    new_credits = agent_data.get('credits', 0)
                    credits_gained = new_credits - old_credits
                    
                    if credits_gained > 0:
                        self.logger.info(f"Received {credits_gained:,} credits for contract acceptance")
                    
                    # Update agent data
                    self.context.update_agent_data({'data': agent_data})
                
                return contract.accepted
            else:
                self.logger.error("Invalid response format from contract acceptance API")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to accept contract {contract.contract_id}: {e}")
            return False
    
    def _record_contract_acceptance(self) -> None:
        """Record metrics for contract acceptance."""
        # This could be expanded to track more detailed metrics
        self.logger.debug("Recording contract acceptance metrics")
        
        # Update strategy based on acceptance
        if self.context.current_contract:
            contract_type = self.context.current_contract.contract_type.value
            payment = self.context.current_contract.terms.total_payment
            
            # Simple strategy adjustment - could be more sophisticated
            if contract_type not in self.context.strategy_config.get('successful_contract_types', []):
                successful_types = self.context.strategy_config.get('successful_contract_types', [])
                successful_types.append(contract_type)
                self.context.strategy_config['successful_contract_types'] = successful_types
    
    def _log_acceptance_details(self, contract) -> None:
        """Log details about the accepted contract."""
        self.logger.info("=== CONTRACT ACCEPTED ===")
        self.logger.info(f"Contract ID: {contract.contract_id}")
        self.logger.info(f"Type: {contract.contract_type.value}")
        self.logger.info(f"Faction: {contract.faction_symbol}")
        self.logger.info(f"Total Payment: {contract.terms.total_payment:,} credits")
        self.logger.info(f"Payment on Accept: {contract.terms.payment_on_accepted:,} credits")
        self.logger.info(f"Payment on Fulfill: {contract.terms.payment_on_fulfilled:,} credits")
        
        # Log deliveries
        self.logger.info("Required Deliveries:")
        for i, delivery in enumerate(contract.terms.deliveries, 1):
            self.logger.info(f"  {i}. {delivery.units_required} {delivery.trade_symbol} "
                           f"to {delivery.destination_symbol}")
        
        # Log deadline
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        time_remaining = contract.terms.deadline - now
        hours_remaining = time_remaining.total_seconds() / 3600
        days_remaining = hours_remaining / 24
        
        self.logger.info(f"Deadline: {contract.terms.deadline}")
        if days_remaining >= 1:
            self.logger.info(f"Time remaining: {days_remaining:.1f} days")
        else:
            self.logger.info(f"Time remaining: {hours_remaining:.1f} hours")
        
        # Log current resources
        if self.context.agent_data:
            self.logger.info(f"Current Credits: {self.context.agent_data.credits:,}")
        
        total_cargo = self.context.get_total_cargo_capacity()
        available_cargo = self.context.get_available_cargo_space()
        self.logger.info(f"Cargo Capacity: {available_cargo}/{total_cargo} available")
        self.logger.info("=========================")