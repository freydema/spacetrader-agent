"""
ACQUIRE_RESOURCES state implementation.

This state handles purchasing ships and upgrading existing ones to meet contract requirements.
"""

from typing import Optional, List, Dict, Any
from models.state_enums import AgentState
from states.base_state import BaseState
from models.ship import Ship


class AcquireResourcesState(BaseState):
    """
    State for acquiring additional resources (ships, upgrades, fuel) to meet contract requirements.
    
    This state:
    1. Analyzes current resource gaps
    2. Finds available shipyards
    3. Evaluates and purchases suitable ships
    4. Ensures ships are fueled and ready
    """
    
    def execute(self) -> Optional[AgentState]:
        """
        Execute the ACQUIRE_RESOURCES state logic.
        
        Returns:
            AgentState: Next state to transition to
        """
        self.log_state_entry()
        
        try:
            # Step 1: Analyze what resources we need
            resource_needs = self._analyze_resource_needs()
            
            if not resource_needs['need_resources']:
                self.logger.info("No additional resources needed - proceeding to contract execution")
                next_state = AgentState.NEGOTIATE_CONTRACT
                self.log_state_exit(next_state)
                return next_state
            
            # Step 2: Find available shipyards
            shipyards = self._find_shipyards()
            
            if not shipyards:
                self.logger.warning("No shipyards found in current system - cannot acquire ships")
                self.logger.info("Agent will wait for contracts that fit current capacity or explore other systems")
                
                # Mark that we tried to acquire resources but failed
                # This prevents immediate retrying
                import time
                self.context.strategy_config['last_acquire_attempt'] = time.time()
                self.context.strategy_config['acquire_failed'] = True
                
                # Fall back to trying contracts with current capacity, but wait longer
                time.sleep(60)  # Wait 1 minute before trying again
                next_state = AgentState.NEGOTIATE_CONTRACT
                self.log_state_exit(next_state)
                return next_state
            
            # Check if any shipyards have ships available
            shipyards_with_ships = [sy for sy in shipyards if len(sy['shipyard_data'].get('ships', [])) > 0]
            if not shipyards_with_ships:
                self.logger.warning("Found shipyards but none have ships in stock - cannot acquire ships")
                self.logger.info("Shipyard inventories refresh periodically - will wait and try again")
                
                # Mark that we tried to acquire resources but failed
                import time
                self.context.strategy_config['last_acquire_attempt'] = time.time()
                self.context.strategy_config['acquire_failed'] = True
                
                # Wait longer since shipyards need time to restock
                time.sleep(300)  # Wait 5 minutes before trying again
                next_state = AgentState.NEGOTIATE_CONTRACT
                self.log_state_exit(next_state)
                return next_state
            
            self.logger.info(f"Found {len(shipyards_with_ships)} shipyards with ships in stock out of {len(shipyards)} total")
            
            # Step 3: Purchase ships if needed
            if resource_needs['need_cargo_capacity']:
                success = self._purchase_cargo_ship(shipyards_with_ships, resource_needs['min_cargo_needed'])
                
                if not success:
                    self.logger.warning("Failed to purchase suitable cargo ship")
                    # Try again later or with different strategy
                    import time
                    time.sleep(30)
                    next_state = AgentState.NEGOTIATE_CONTRACT
                    self.log_state_exit(next_state)
                    return next_state
            
            # Step 4: Refuel ships if needed
            self._ensure_ships_fueled()
            
            # Step 5: Update ship data
            self._refresh_ship_data()
            
            self.logger.info("Successfully acquired additional resources")
            next_state = AgentState.NEGOTIATE_CONTRACT
            self.log_state_exit(next_state)
            return next_state
            
        except Exception as e:
            self.logger.error(f"Error in ACQUIRE_RESOURCES state: {e}")
            return AgentState.ERROR_RECOVERY
    
    def _analyze_resource_needs(self) -> Dict[str, Any]:
        """
        Analyze what resources the agent currently needs.
        
        Returns:
            Dict with analysis of resource needs
        """
        self.logger.info("Analyzing resource needs...")
        
        current_capacity = self.context.get_total_cargo_capacity()
        ships_needing_fuel = [ship for ship in self.context.ships if ship.fuel.needs_refuel]
        
        # Simple heuristic: if we're in this state, we probably need more cargo capacity
        # In a real implementation, this could be more sophisticated
        target_capacity = max(60, current_capacity + 20)  # At least 60 units or 20 more than current
        
        needs = {
            'need_resources': False,
            'need_cargo_capacity': False,
            'need_fuel': len(ships_needing_fuel) > 0,
            'min_cargo_needed': 0,
            'current_capacity': current_capacity,
            'target_capacity': target_capacity,
            'ships_needing_fuel': ships_needing_fuel
        }
        
        if current_capacity < target_capacity:
            needs['need_resources'] = True
            needs['need_cargo_capacity'] = True
            needs['min_cargo_needed'] = target_capacity - current_capacity
        
        if ships_needing_fuel:
            needs['need_resources'] = True
        
        self.logger.info(f"Resource analysis: Current capacity: {current_capacity}, "
                        f"Target: {target_capacity}, Need fuel: {len(ships_needing_fuel)} ships")
        
        return needs
    
    def _find_shipyards(self) -> List[Dict[str, Any]]:
        """
        Find shipyards where we can purchase ships.
        
        Returns:
            List of shipyard information
        """
        self.logger.info("Finding available shipyards...")
        
        shipyards = []
        
        try:
            # Start with headquarters system
            if self.context.agent_data:
                headquarters = self.context.agent_data.headquarters
                system_symbol = self.api_client.extract_system_from_waypoint(headquarters)
                
                self.logger.info(f"Searching for shipyards in system {system_symbol} (HQ: {headquarters})")
                
                # Get ALL waypoints in the headquarters system (with pagination)
                all_waypoints = []
                page = 1
                limit = 20
                
                while True:
                    response = self.api_client.get_system_waypoints(system_symbol, page=page, limit=limit)
                    waypoints = response.get('data', [])
                    
                    if not waypoints:
                        break
                    
                    all_waypoints.extend(waypoints)
                    self.logger.debug(f"Page {page}: Got {len(waypoints)} waypoints")
                    
                    # Check if there are more pages
                    meta = response.get('meta', {})
                    total_pages = meta.get('total', 0) // limit + (1 if meta.get('total', 0) % limit > 0 else 0)
                    
                    if page >= total_pages or len(waypoints) < limit:
                        break
                    
                    page += 1
                
                self.logger.info(f"Found {len(all_waypoints)} total waypoints in system {system_symbol} across {page} pages")
                
                # Find waypoints with shipyards
                for waypoint in all_waypoints:
                    waypoint_symbol = waypoint.get('symbol')
                    traits = waypoint.get('traits', [])
                    trait_symbols = [trait.get('symbol') for trait in traits]
                    
                    self.logger.info(f"Waypoint {waypoint_symbol} has traits: {trait_symbols}")
                    
                    has_shipyard = any(trait.get('symbol') == 'SHIPYARD' for trait in traits)
                    
                    if has_shipyard:
                        self.logger.info(f"Found shipyard at {waypoint_symbol}")
                        
                        try:
                            # Get shipyard details
                            shipyard_response = self.api_client.get_shipyard(system_symbol, waypoint_symbol)
                            shipyard_data = shipyard_response.get('data', {})
                            
                            ships_available = len(shipyard_data.get('ships', []))
                            self.logger.info(f"Shipyard at {waypoint_symbol} has {ships_available} ships available")
                            
                            # Log details of available ships
                            ships = shipyard_data.get('ships', [])
                            for ship_info in ships:
                                ship_type = ship_info.get('type', 'UNKNOWN')
                                price = ship_info.get('purchasePrice', 0)
                                cargo_info = ship_info.get('cargo', {})
                                cargo_capacity = cargo_info.get('capacity', 0)
                                
                                self.logger.info(f"  - {ship_type}: {price:,} credits, {cargo_capacity} cargo capacity")
                            
                            shipyards.append({
                                'waypoint_symbol': waypoint_symbol,
                                'system_symbol': system_symbol,
                                'shipyard_data': shipyard_data
                            })
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to get shipyard details for {waypoint_symbol}: {e}")
                            continue
            
            self.logger.info(f"Found {len(shipyards)} accessible shipyards")
            return shipyards
            
        except Exception as e:
            self.logger.error(f"Failed to find shipyards: {e}")
            return []
    
    def _purchase_cargo_ship(self, shipyards: List[Dict[str, Any]], min_cargo_needed: int) -> bool:
        """
        Purchase a ship with good cargo capacity.
        
        Args:
            shipyards: List of available shipyards
            min_cargo_needed: Minimum additional cargo capacity needed
            
        Returns:
            bool: True if purchase successful
        """
        self.logger.info(f"Looking for cargo ship with at least {min_cargo_needed} additional capacity...")
        
        if not self.context.agent_data:
            self.logger.error("No agent data available for ship purchase")
            return False
        
        available_credits = self.context.agent_data.credits
        safety_reserve = self.context.strategy_config.get('safety_credit_reserve', 10000)
        purchasable_credits = available_credits - safety_reserve
        
        self.logger.info(f"Available credits for ship purchase: {purchasable_credits:,}")
        
        best_ship = None
        best_shipyard = None
        best_value = 0  # Cargo capacity per credit
        
        for shipyard in shipyards:
            shipyard_data = shipyard['shipyard_data']
            ships = shipyard_data.get('ships', [])
            
            for ship_info in ships:
                ship_type = ship_info.get('type')
                price = ship_info.get('purchasePrice', 0)
                
                if price > purchasable_credits:
                    self.logger.debug(f"Ship {ship_type} costs {price:,}, exceeds budget")
                    continue
                
                # Get actual cargo capacity from ship's cargo specification
                cargo_info = ship_info.get('cargo', {})
                cargo_capacity = cargo_info.get('capacity', 0)
                
                self.logger.debug(f"Ship {ship_type} has {cargo_capacity} cargo capacity (from cargo spec)")
                
                # Skip ships with no cargo capacity (like surveyors)
                if cargo_capacity <= 0:
                    self.logger.debug(f"Ship {ship_type} has no cargo capacity - skipping")
                    continue
                
                if cargo_capacity < min_cargo_needed:
                    self.logger.debug(f"Ship {ship_type} has {cargo_capacity} cargo, need at least {min_cargo_needed}")
                    continue
                
                # Calculate value (cargo per credit)
                value = cargo_capacity / max(price, 1)
                
                self.logger.info(f"Ship option: {ship_type} - {cargo_capacity} cargo, {price:,} credits, value: {value:.6f}")
                
                if value > best_value:
                    best_ship = ship_info
                    best_shipyard = shipyard
                    best_value = value
        
        if not best_ship:
            self.logger.warning("No suitable ships found within budget")
            return False
        
        # Purchase the best ship
        return self._execute_ship_purchase(best_ship, best_shipyard)
    
    def _execute_ship_purchase(self, ship_info: Dict[str, Any], shipyard: Dict[str, Any]) -> bool:
        """
        Execute the actual ship purchase.
        
        Args:
            ship_info: Information about the ship to purchase
            shipyard: Shipyard where the ship is available
            
        Returns:
            bool: True if purchase successful
        """
        ship_type = ship_info.get('type')
        price = ship_info.get('purchasePrice', 0)
        waypoint_symbol = shipyard['waypoint_symbol']
        
        self.logger.info(f"Attempting to purchase {ship_type} for {price:,} credits at {waypoint_symbol}")
        
        try:
            # First, move a ship to the shipyard if needed
            ship_at_shipyard = self._get_ship_at_waypoint(waypoint_symbol)
            
            if not ship_at_shipyard:
                # Move our closest ship to the shipyard
                success = self._move_ship_to_waypoint(waypoint_symbol)
                if not success:
                    self.logger.error(f"Failed to move ship to shipyard at {waypoint_symbol}")
                    return False
                
                ship_at_shipyard = self._get_ship_at_waypoint(waypoint_symbol)
            
            if not ship_at_shipyard:
                self.logger.error("No ship available at shipyard for purchase")
                return False
            
            # Make the purchase
            response = self.api_client.purchase_ship(ship_type, waypoint_symbol)
            
            if response and 'data' in response:
                ship_data = response['data'].get('ship', {})
                agent_data = response['data'].get('agent', {})
                transaction = response['data'].get('transaction', {})
                
                if ship_data:
                    new_ship = Ship.from_api_response(ship_data)
                    self.context.ships.append(new_ship)
                    
                    self.logger.info(f"✅ Successfully purchased ship {new_ship.symbol}")
                    self.logger.info(f"   Type: {ship_type}")
                    self.logger.info(f"   Cargo Capacity: {new_ship.cargo_capacity}")
                    self.logger.info(f"   Price: {price:,} credits")
                
                # Update agent credits
                if agent_data:
                    old_credits = self.context.agent_data.credits
                    self.context.update_agent_data({'data': agent_data})
                    new_credits = self.context.agent_data.credits
                    
                    self.logger.info(f"Credits: {old_credits:,} → {new_credits:,} (-{old_credits - new_credits:,})")
                
                return True
            else:
                self.logger.error("Invalid response from ship purchase API")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to purchase ship {ship_type}: {e}")
            return False
    
    def _get_ship_at_waypoint(self, waypoint_symbol: str) -> Optional[Ship]:
        """Get a ship that is at the specified waypoint."""
        for ship in self.context.ships:
            if ship.nav.waypoint_symbol == waypoint_symbol:
                return ship
        return None
    
    def _move_ship_to_waypoint(self, waypoint_symbol: str) -> bool:
        """Move a ship to the specified waypoint."""
        # Find the best ship to move (closest, with fuel, etc.)
        best_ship = None
        
        for ship in self.context.ships:
            if ship.nav.is_in_transit:
                continue  # Skip ships in transit
            
            if ship.fuel.current <= 0:
                continue  # Skip ships without fuel
            
            # For now, just pick the first available ship
            best_ship = ship
            break
        
        if not best_ship:
            self.logger.warning("No ship available to move to shipyard")
            return False
        
        try:
            self.logger.info(f"Moving ship {best_ship.symbol} to {waypoint_symbol}")
            
            # Make sure ship is in orbit
            if best_ship.nav.is_docked:
                self.api_client.orbit_ship(best_ship.symbol)
            
            # Navigate to waypoint
            response = self.api_client.navigate_ship(best_ship.symbol, waypoint_symbol)
            
            if response:
                self.logger.info(f"Ship {best_ship.symbol} navigating to {waypoint_symbol}")
                # In a real implementation, we might wait for arrival
                return True
            
        except Exception as e:
            self.logger.error(f"Failed to move ship to waypoint: {e}")
        
        return False
    
    def _ensure_ships_fueled(self) -> None:
        """Ensure all ships have adequate fuel."""
        for ship in self.context.ships:
            if ship.fuel.needs_refuel and ship.nav.is_docked:
                try:
                    self.logger.info(f"Refueling ship {ship.symbol}")
                    self.api_client.refuel_ship(ship.symbol)
                except Exception as e:
                    self.logger.warning(f"Failed to refuel ship {ship.symbol}: {e}")
    
    def _refresh_ship_data(self) -> None:
        """Refresh ship data from the API."""
        try:
            response = self.api_client.get_my_ships()
            ships_data = response.get('data', [])
            
            self.context.ships = [
                Ship.from_api_response(ship_data)
                for ship_data in ships_data
            ]
            
            total_capacity = self.context.get_total_cargo_capacity()
            self.logger.info(f"Updated ship data - Total cargo capacity: {total_capacity}")
            
        except Exception as e:
            self.logger.error(f"Failed to refresh ship data: {e}")


# Need to add the purchase_ship method to the API client