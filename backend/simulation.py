# simulation.py
import numpy as np
import os
import random
from random import choice
import json
from dotenv import load_dotenv
import asyncio
import time
from litellm_client import create_client as create_llm_client

# Load environment variables
load_dotenv()
IO_API_KEY = os.getenv("IO_SECRET_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# LiteLLM API base
LITELLM_API_BASE = "http://host.orb.internal:4000/v1"

# Initialize model clients via LiteLLM
def get_openai_client():
    return create_llm_client(api_key=OPENAI_API_KEY, api_base=LITELLM_API_BASE)

def get_gemini_client():
    return create_llm_client(api_key=GEMINI_API_KEY, api_base=LITELLM_API_BASE)

def get_mistral_client():
    return create_llm_client(api_key=MISTRAL_API_KEY, api_base=LITELLM_API_BASE)

# Initialize model clients
openai_client = get_openai_client()
gemini_client = get_gemini_client()
mistral_client = get_mistral_client()

class SimpleAntAgent:
    def __init__(self, unique_id, model, is_llm_controlled=True):
        self.unique_id = unique_id
        self.model = model
        self.carrying_food = False
        self.pos = (np.random.randint(model.width), np.random.randint(model.height))
        self.is_llm_controlled = is_llm_controlled
        self.api_calls = 0
        self.move_history = []
        self.food_collected_count = 0
        self.steps_since_food = 0  # For recruitment pheromone

    def step(self, guided_pos=None):
        x, y = self.pos
        possible_steps = self.model.get_neighborhood(x, y)
        new_position = self.pos

        # Pheromone deposition before moving (based on current state)
        if self.carrying_food:
            # Deposit trail pheromone when carrying food (returning from food source)
            self.model.deposit_pheromone(self.pos, 'trail', self.model.trail_deposit * 0.5)
        elif self.model.is_food_at(self.pos):
            # Deposit trail pheromone when at a food source
            self.model.deposit_pheromone(self.pos, 'trail', self.model.trail_deposit * 1.5)

        # PRIORITY 1: Pick up food if we're standing on it (even with predators nearby!)
        if self.model.is_food_at(self.pos) and not self.carrying_food:
            new_position = self.pos  # Stay to pick up food
        else:
            # Check for immediate predator threat (second priority)
            nearby_predators = [p for p in self.model.predators 
                               if abs(p.pos[0] - x) <= 2 and abs(p.pos[1] - y) <= 2]
            
            if nearby_predators and possible_steps:
                # ESCAPE! Move away from nearest predator
                nearest_predator = min(nearby_predators, 
                                     key=lambda p: abs(p.pos[0] - x) + abs(p.pos[1] - y))
                # Find position that maximizes distance from predator
                escape_pos = max(possible_steps + [self.pos], 
                               key=lambda pos: abs(pos[0] - nearest_predator.pos[0]) + abs(pos[1] - nearest_predator.pos[1]))
                new_position = escape_pos
                # Deposit alarm pheromone when escaping
                self.model.deposit_pheromone(self.pos, 'alarm', self.model.alarm_deposit * 2)
            elif guided_pos and guided_pos in possible_steps + [self.pos]:
                # Queen guidance takes priority (when not escaping)
                new_position = guided_pos
            elif self.is_llm_controlled and self.model.io_client and self.model.api_enabled:
                try:
                    action = self.ask_io_for_decision(self.model.prompt_style, self.model.selected_model)
                    self.api_calls += 1
                    if action == "toward" and possible_steps:
                        target_food = self._find_nearest_food()
                        if target_food:
                            new_position = self._step_toward(self.pos, target_food)
                        else:
                            new_position = choice(possible_steps)
                    elif action == "random" and possible_steps:
                        new_position = choice(possible_steps)
                    elif action == "stay":
                        new_position = self.pos
                    else:
                        new_position = choice(possible_steps) if possible_steps else self.pos
                except Exception as e:
                    # Deposit alarm pheromone on API error
                    self.model.deposit_pheromone(self.pos, 'alarm', self.model.alarm_deposit * 1.5)
                    self.model.log_error(f"API call failed for ant {self.unique_id}: {str(e)}. Falling back to rule-based.")
                    new_position = self._use_rule_based_behavior(possible_steps)
            else:
                # Rule-based behavior
                new_position = self._use_rule_based_behavior(possible_steps)

        self.move_history.append(self.pos)
        self.pos = new_position

        # Food pickup/drop logic
        if self.model.is_food_at(self.pos) and not self.carrying_food:
            # Pick up food
            self.carrying_food = True
            self.model.collect_food(self.pos, self.is_llm_controlled)
            self.food_collected_count += 1
            self.steps_since_food = 0
            # Deposit strong trail pheromone upon successful pickup
            self.model.deposit_pheromone(self.pos, 'trail', self.model.trail_deposit * 2)
        # Food drop at nest for LLM ants (they never got drop logic before)
        if self.carrying_food and self.is_llm_controlled:
            nest_x, nest_y = self.model.width // 2, self.model.height // 2
            dist_to_nest = abs(self.pos[0] - nest_x) + abs(self.pos[1] - nest_y)
            if dist_to_nest <= 2:  # Within 2 cells of nest
                self.carrying_food = False
                self.model.metrics['food_collected'] += 1
                self.model.metrics['food_collected_by_llm'] += 1
                # Strong trail pheromone back toward food
                self.model.deposit_pheromone(self.pos, 'trail', self.model.trail_deposit * 3)
        else:
            self.steps_since_food += 1
            # If LLM ant hasn't found food for a while, deposit recruitment pheromone
            if self.is_llm_controlled and self.steps_since_food > 10 and not self.carrying_food:
                self.model.deposit_pheromone(self.pos, 'recruitment', self.model.recruitment_deposit)
        
        # Drop food at nest/home for both LLM and rule-based ants
        if self.carrying_food:
            home = (self.model.width // 2, self.model.height // 2)
            # Drop food if within Manhattan distance 2 of nest center
            if abs(self.pos[0] - home[0]) <= 2 and abs(self.pos[1] - home[1]) <= 2:
                if self.is_llm_controlled or random.random() < 0.3:
                    self.carrying_food = False
                    self.model.metrics['food_collected'] += 1
                    # Deposit trail pheromone at nest when dropping food
                    self.model.deposit_pheromone(self.pos, 'trail', self.model.trail_deposit * 1.5)

    def _use_rule_based_behavior(self, possible_steps):
        """Enhanced rule-based behavior with home/nest awareness"""
        if self.model.is_food_at(self.pos) and not self.carrying_food:
            return self.pos  # Stay to pick up food
        elif self.carrying_food:
            # Move towards nest/home (center of grid)
            home = (self.model.width // 2, self.model.height // 2)
            return self._step_toward(self.pos, home)
        else:
            # Look for nearest food and move towards it, or move randomly
            target_food = self._find_nearest_food()
            if target_food:
                return self._step_toward(self.pos, target_food)
            else:
                return choice(possible_steps) if possible_steps else self.pos

    def _find_nearest_food(self):
        if not self.model.foods:
            return None
        return min(self.model.foods,
                   key=lambda f: abs(f[0]-self.pos[0]) + abs(f[1]-self.pos[1]))

    def _step_toward(self, start, target):
        x, y = start
        tx, ty = target
        possible_moves = self.model.get_neighborhood(x, y)
        if not possible_moves:
            return start
        return min(possible_moves, key=lambda n: abs(n[0]-tx)+abs(n[1]-ty))

    def ask_io_for_decision(self, prompt_style_param, selected_model_param):
        x, y = self.pos
        food_nearby = any(
            abs(fx - x) <= 1 and abs(fy - y) <= 1
            for fx, fy in self.model.get_food_positions()
        )
        
        # Get local pheromone information
        local_pheromones = self.model.get_local_pheromones(self.pos, radius=2)
        
        # Check for nearby predators
        nearby_predators = [p for p in self.model.predators 
                           if abs(p.pos[0] - x) <= 3 and abs(p.pos[1] - y) <= 3]
        
        pheromone_info = (
            f"Local Pheromones (radius 2): "
            f"Trail: {local_pheromones['trail']:.2f}, "
            f"Alarm: {local_pheromones['alarm']:.2f}, "
            f"Recruitment: {local_pheromones['recruitment']:.2f}, "
            f"Fear: {local_pheromones.get('fear', 0):.2f}. "
            f"Predators nearby: {len(nearby_predators)}. "
        )

        if prompt_style_param == "Structured":
            prompt = (
                f"You are an ant at position ({x},{y}) on a {self.model.width}x{self.model.height} grid. "
                f"Food nearby: {food_nearby}. Carrying food: {self.carrying_food}. "
                f"{pheromone_info}"
                "Should you move 'toward' food, move 'random', or 'stay'? "
                "Consider: High trail=good path, high alarm=danger, high recruitment=help needed, high fear=predators! "
                "PRIORITY: Avoid areas with high fear pheromone (predators). "
                "Reply with only one word: 'toward', 'random', or 'stay'."
            )
        elif prompt_style_param == "Autonomous":
            prompt = (
                f"As an autonomous ant foraging for food, my current state is: "
                f"Position: ({x},{y}), "
                f"Food available nearby: {food_nearby}, "
                f"Currently carrying food: {self.carrying_food}. "
                f"{pheromone_info}"
                "What is the best action? Choose: 'toward', 'random', or 'stay'. "
                "Pheromone signals: Trail=good path, alarm=danger, recruitment=help needed, fear=PREDATORS (avoid!). "
                "Survival is priority #1 - avoid fear pheromone areas."
            )
        else:  # Adaptive
            efficiency = self.food_collected_count
            prompt = (
                f"Ant {self.unique_id} has collected {efficiency} food items. "
                f"Current position: ({x},{y}). "
                f"Food nearby: {food_nearby}. "
                f"Carrying food: {self.carrying_food}. "
                f"{pheromone_info}"
                "Best action? Options: 'toward', 'random', 'stay'. "
                "Pheromone guide: Follow trails, avoid alarms/fear (predators!), respond to recruitment. "
                "Stay alive first, then collect food."
            )

        try:
            # Route to appropriate model API based on model name
            action = None
            
            # OpenAI models (gpt-4o, gpt-4o-mini)
            if selected_model_param.startswith("gpt-") and openai_client:
                response = openai_client.chat.completions.create(
                    model=selected_model_param,
                    messages=[
                        {"role": "system", "content": "You are an intelligent ant. Respond with one word: toward, random, or stay."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=10,
                    timeout=10
                )
                action = response.choices[0].message.content.strip().lower()
            
            # Gemini models
            elif selected_model_param.startswith("gemini-") and genai:
                model = genai.GenerativeModel(selected_model_param)
                response = model.generate_content(
                    f"You are an intelligent ant. Respond with one word: toward, random, or stay.\n\n{prompt}",
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=10,
                    )
                )
                action = response.text.strip().lower()
            
            # Mistral models
            elif selected_model_param.startswith("mistral-") and mistral_client:
                response = mistral_client.chat.complete(
                    model=selected_model_param,
                    messages=[
                        {"role": "system", "content": "You are an intelligent ant. Respond with one word: toward, random, or stay."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=10
                )
                action = response.choices[0].message.content.strip().lower()
            
            # DeepSeek models (OpenAI-compatible via IO.NET)
            elif selected_model_param.startswith("deepseek-") and self.model.io_client:
                response = self.model.io_client.chat.completions.create(
                    model=selected_model_param,
                    messages=[
                        {"role": "system", "content": "You are an intelligent ant. Respond with one word: toward, random, or stay."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_completion_tokens=10,
                    timeout=10
                )
                action = response.choices[0].message.content.strip().lower()
            
            # IO.NET models (meta-llama, etc.)
            elif self.model.io_client:
                response = self.model.io_client.chat.completions.create(
                    model=selected_model_param,
                    messages=[
                        {"role": "system", "content": "You are an intelligent ant. Respond with one word: toward, random, or stay."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_completion_tokens=10,
                    timeout=10
                )
                action = response.choices[0].message.content.strip().lower()
            
            # Return valid action or default to random
            return action if action in ["toward", "random", "stay"] else "random"
            
        except Exception as e:
            # Deposit alarm pheromone on API error
            self.model.deposit_pheromone(self.pos, 'alarm', self.model.alarm_deposit * 1.5)
            self.model.log_error(f"LLM call failed for Ant {self.unique_id} with model {selected_model_param}: {str(e)}")
            return "random"

# Predator agent class
class PredatorAgent:
    def __init__(self, unique_id, model, is_llm_controlled=True):
        self.unique_id = unique_id
        self.model = model
        self.pos = (np.random.randint(model.width), np.random.randint(model.height))
        self.is_llm_controlled = is_llm_controlled
        self.api_calls = 0
        self.energy = 100  # Energy for hunting
        self.hunt_cooldown = 0  # Cooldown between hunts
        self.ants_caught = 0
        self.move_history = []
        self.hunting_range = 2  # How close predator needs to be to catch ant

    def step(self):
        x, y = self.pos
        possible_steps = self.model.get_neighborhood(x, y)
        new_position = self.pos

        # Reduce cooldown and restore energy over time
        if self.hunt_cooldown > 0:
            self.hunt_cooldown -= 1
        if self.energy < 100:
            self.energy = min(100, self.energy + 2)

        # Deposit fear pheromone at current position
        self.model.deposit_pheromone(self.pos, 'fear', self.model.fear_deposit)

        if self.is_llm_controlled and self.model.io_client and self.model.api_enabled:
            try:
                action = self.ask_io_for_decision(self.model.prompt_style, self.model.selected_model)
                self.api_calls += 1
                if action == "hunt" and possible_steps:
                    target_ant = self._find_nearest_ant()
                    if target_ant:
                        new_position = self._step_toward(self.pos, target_ant.pos)
                    else:
                        new_position = choice(possible_steps)
                elif action == "patrol" and possible_steps:
                    # Patrol behavior - move to areas with less fear pheromone
                    new_position = self._patrol_behavior(possible_steps)
                elif action == "rest":
                    new_position = self.pos
                else:
                    new_position = choice(possible_steps) if possible_steps else self.pos
            except Exception as e:
                # Fallback to rule-based behavior on API error
                new_position = self._use_rule_based_behavior(possible_steps)
        else:
            # Rule-based predator behavior
            new_position = self._use_rule_based_behavior(possible_steps)

        self.move_history.append(self.pos)
        self.pos = new_position

        # Try to catch ants in hunting range
        self._attempt_hunt()

    def _find_nearest_ant(self):
        if not self.model.ants:
            return None
        return min(self.model.ants,
                   key=lambda ant: abs(ant.pos[0]-self.pos[0]) + abs(ant.pos[1]-self.pos[1]))

    def _step_toward(self, start, target):
        x, y = start
        tx, ty = target
        possible_moves = self.model.get_neighborhood(x, y)
        if not possible_moves:
            return start
        return min(possible_moves, key=lambda n: abs(n[0]-tx)+abs(n[1]-ty))

    def _patrol_behavior(self, possible_steps):
        # Move to areas with less fear pheromone to spread hunting pressure
        best_pos = self.pos
        min_fear = float('inf')
        
        for pos in possible_steps + [self.pos]:
            if 0 <= pos[0] < self.model.width and 0 <= pos[1] < self.model.height:
                fear_level = self.model.pheromone_map['fear'][pos[0], pos[1]]
                if fear_level < min_fear:
                    min_fear = fear_level
                    best_pos = pos
        
        return best_pos

    def _use_rule_based_behavior(self, possible_steps):
        # Rule-based: hunt if energy is high, patrol otherwise
        if self.energy > 50 and self.hunt_cooldown == 0:
            target_ant = self._find_nearest_ant()
            if target_ant:
                # Move toward nearest ant
                return self._step_toward(self.pos, target_ant.pos)
        
        # Otherwise patrol
        return self._patrol_behavior(possible_steps) if possible_steps else self.pos

    def _attempt_hunt(self):
        if self.hunt_cooldown > 0 or self.energy < 30:
            return
        
        # Check for ants within hunting range
        for ant in self.model.ants[:]:  # Use slice to avoid modification during iteration
            distance = abs(ant.pos[0] - self.pos[0]) + abs(ant.pos[1] - self.pos[1])
            if distance <= self.hunting_range:
                # Successful hunt!
                self.model.ants.remove(ant)
                self.ants_caught += 1
                self.energy = min(100, self.energy + 20)  # Gain energy from hunting
                self.hunt_cooldown = 5  # Cooldown before next hunt
                self.model.metrics["ants_caught"] += 1
                
                # Update ant type specific metrics
                if ant.is_llm_controlled:
                    self.model.metrics["llm_ants_caught"] += 1
                else:
                    self.model.metrics["rule_ants_caught"] += 1
                
                # Deposit strong fear pheromone at hunt location
                self.model.deposit_pheromone(self.pos, 'fear', self.model.fear_deposit * 3)
                break  # Only catch one ant per step

    def ask_io_for_decision(self, prompt_style_param, selected_model_param):
        x, y = self.pos
        nearby_ants = [ant for ant in self.model.ants 
                      if abs(ant.pos[0] - x) <= 3 and abs(ant.pos[1] - y) <= 3]
        
        # Get local pheromone information
        local_pheromones = self.model.get_local_pheromones(self.pos, radius=2)
        
        pheromone_info = (
            f"Local Pheromones: "
            f"Fear: {local_pheromones.get('fear', 0):.2f}, "
            f"Trail: {local_pheromones.get('trail', 0):.2f}. "
        )

        if prompt_style_param == "Structured":
            prompt = (
                f"You are a predator at position ({x},{y}) on a {self.model.width}x{self.model.height} grid. "
                f"Nearby ants: {len(nearby_ants)}. Energy: {self.energy}/100. Hunt cooldown: {self.hunt_cooldown}. "
                f"{pheromone_info}"
                "Should you 'hunt' ants, 'patrol' territory, or 'rest'? "
                f"High fear pheromone means you've been here recently. Trail pheromone indicates ant activity. "
                "Reply with only one word: 'hunt', 'patrol', or 'rest'."
            )
        elif prompt_style_param == "Autonomous":
            prompt = (
                f"As an autonomous predator, my state is: "
                f"Position: ({x},{y}), "
                f"Nearby prey: {len(nearby_ants)} ants, "
                f"Energy: {self.energy}/100, Hunt cooldown: {self.hunt_cooldown}. "
                f"{pheromone_info}"
                "What is the optimal strategy? Choose: 'hunt', 'patrol', or 'rest'. "
                "Consider energy management and territorial coverage."
            )
        else:  # Adaptive
            success_rate = self.ants_caught / max(1, len(self.move_history))
            prompt = (
                f"Predator {self.unique_id} has caught {self.ants_caught} ants with success rate {success_rate:.2f}. "
                f"Current position: ({x},{y}). "
                f"Nearby ants: {len(nearby_ants)}. Energy: {self.energy}/100. "
                f"{pheromone_info}"
                "Best hunting strategy? Options: 'hunt', 'patrol', 'rest'. "
                "Adapt based on your success rate and current conditions."
            )

        try:
            response = self.model.io_client.chat.completions.create(
                model=selected_model_param,
                messages=[
                    {"role": "system", "content": "You are an intelligent predator. Respond with only one word: hunt, patrol, or rest."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_completion_tokens=10
            )
            action = response.choices[0].message.content.strip().lower()
            return action if action in ["hunt", "patrol", "rest"] else "hunt"
        except Exception as e:
            return "hunt"  # Default to hunting on error


class QueenAnt:
    """Enhanced Queen with pheromone awareness"""
    def __init__(self, model, use_llm=False):
        self.model = model
        self.use_llm = use_llm

    def guide(self, selected_model_param) -> dict:
        guidance = {}
        if not self.model.foods:
            self.model.queen_llm_anomaly_rep = "No food remaining for guidance"
            return guidance

        if self.use_llm and self.model.io_client and self.model.api_enabled:
            return self._guide_with_llm(selected_model_param)
        else:
            return self._guide_with_heuristic()

    def _guide_with_heuristic(self) -> dict:
        guidance = {}
        ants = self.model.ants
        foods = list(self.model.foods)
        
        if not foods:
            self.model.queen_llm_anomaly_rep = "No food remaining - no guidance needed"
            return guidance
        
        # More sophisticated heuristic guidance
        for ant in ants:
            if ant.carrying_food:
                # If ant is carrying food, guide it toward the nest (center)
                nest_pos = (self.model.width // 2, self.model.height // 2)
                possible_moves = self.model.get_neighborhood(*ant.pos) + [ant.pos]
                if possible_moves:
                    best_step = min(
                        possible_moves,
                        key=lambda n: abs(n[0]-nest_pos[0]) + abs(n[1]-nest_pos[1])
                    )
                    guidance[ant.unique_id] = best_step
            else:
                # If ant is not carrying food, guide it toward nearest food
                if foods:
                    target = min(
                        foods,
                        key=lambda f: abs(f[0]-ant.pos[0]) + abs(f[1]-ant.pos[1])
                    )
                    possible_moves = self.model.get_neighborhood(*ant.pos) + [ant.pos]
                    if possible_moves:
                        best_step = min(
                            possible_moves,
                            key=lambda n: abs(n[0]-target[0]) + abs(n[1]-target[1])
                        )
                        guidance[ant.unique_id] = best_step
        
        self.model.queen_llm_anomaly_rep = f"Queen heuristic guidance: Directed {len(guidance)} ants ({len([a for a in ants if a.carrying_food])} carrying food, {len([a for a in ants if not a.carrying_food])} foraging)"
        return guidance

    def _guide_with_llm(self, selected_model_param) -> dict:
        guidance = {}
        
        if not self.model.io_client:
            self.model.log_error("IO Client not initialized for Queen Ant. Using heuristic guidance.")
            return self._guide_with_heuristic()

        # Summarize global pheromone information for the Queen
        max_trail_val = np.max(self.model.pheromone_map['trail'])
        max_alarm_val = np.max(self.model.pheromone_map['alarm'])
        max_recruitment_val = np.max(self.model.pheromone_map['recruitment'])

        # Find locations of max pheromones
        trail_locs = np.argwhere(self.model.pheromone_map['trail'] == max_trail_val)
        alarm_locs = np.argwhere(self.model.pheromone_map['alarm'] == max_alarm_val)
        recruitment_locs = np.argwhere(self.model.pheromone_map['recruitment'] == max_recruitment_val)

        trail_pos_str = f"({trail_locs[0][0]}, {trail_locs[0][1]})" if trail_locs.size > 0 else "N/A"
        alarm_pos_str = f"({alarm_locs[0][0]}, {alarm_locs[0][1]})" if alarm_locs.size > 0 else "N/A"
        recruitment_pos_str = f"({recruitment_locs[0][0]}, {recruitment_locs[0][1]})" if recruitment_locs.size > 0 else "N/A"

        prompt = f"""You are a Queen Ant. Guide your worker ants efficiently.

Current situation:
- Step: {self.model.step_count}
- Grid: {self.model.width}x{self.model.height}
- Ants: {len(self.model.ants)} 
- Food: {len(self.model.foods)} remaining

Pheromone Summary:
- Max Trail: {max_trail_val:.2f} at {trail_pos_str} (success paths)
- Max Alarm: {max_alarm_val:.2f} at {alarm_pos_str} (problems)
- Max Recruitment: {max_recruitment_val:.2f} at {recruitment_pos_str} (help needed)

Respond with JSON: {{"guidance": {{"0": [x,y], "1": [x,y]}}, "report": "brief status"}}

Ant positions:"""
        
        for ant in self.model.ants[:5]:  # Limit to avoid token limits
            nearby_food = [f for f in self.model.foods if abs(f[0]-ant.pos[0]) <= 2 and abs(f[1]-ant.pos[1]) <= 2]
            prompt += f"\nAnt {ant.unique_id}: at {ant.pos}, carrying={ant.carrying_food}, nearby_food={len(nearby_food)}"

        try:
            response = self.model.io_client.chat.completions.create(
                model=selected_model_param,
                messages=[
                    {"role": "system", "content": "You are a Queen Ant. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_completion_tokens=300,
                timeout=15
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON from response
            try:
                if '{' in response_text and '}' in response_text:
                    start = response_text.find('{')
                    end = response_text.rfind('}') + 1
                    json_str = response_text[start:end]
                    parsed_response = json.loads(json_str)
                    
                    raw_guidance = parsed_response.get("guidance", {})
                    report = parsed_response.get("report", "Queen provided guidance")
                    
                    # Validate and convert guidance
                    for ant_id_str, pos in raw_guidance.items():
                        try:
                            ant_id = int(ant_id_str)
                            if isinstance(pos, list) and len(pos) == 2:
                                ant = next((a for a in self.model.ants if a.unique_id == ant_id), None)
                                if ant:
                                    proposed_pos = tuple(pos)
                                    valid_moves = self.model.get_neighborhood(*ant.pos) + [ant.pos]
                                    if proposed_pos in valid_moves:
                                        guidance[ant_id] = proposed_pos
                        except (ValueError, TypeError, IndexError):
                            continue
                    
                    self.model.queen_llm_anomaly_rep = f"Queen LLM: {report} (guided {len(guidance)} ants)"
                    return guidance
                else:
                    raise json.JSONDecodeError("No JSON found", response_text, 0)
                    
            except json.JSONDecodeError:
                self.model.queen_llm_anomaly_rep = "Queen LLM: Invalid JSON response, using heuristic"
                return self._guide_with_heuristic()
                
        except Exception as e:
            self.model.queen_llm_anomaly_rep = f"Queen LLM: API error ({str(e)[:50]}), using heuristic"
            return self._guide_with_heuristic()


class SimpleForagingModel:
    def __init__(self, width, height, N_ants, N_food,
                 agent_type="LLM-Powered", with_queen=False, use_llm_queen=False,
                 selected_model_param="meta-llama/Llama-3.3-70B-Instruct", prompt_style_param="Adaptive",
                 N_predators=0, predator_type="LLM-Powered"):
        self.width = width
        self.height = height
        
        # Initialize error logging FIRST
        self.errors = []
        
        # Use set for foods for better performance
        self.foods = set()
        
        # Spawn food in spatial clusters (more realistic than pure random)
        # Food sources in nature are patchy, not uniformly distributed
        n_clusters = max(2, min(4, N_food // 4))  # 2-4 clusters depending on total food
        cluster_radius = max(2, min(width, height) // 5)  # cluster spread radius
        
        # Avoid placing clusters too close to nest (center) so ants must actually forage
        nest_cx, nest_cy = width // 2, height // 2
        min_dist_from_nest = max(3, min(width, height) // 4)
        
        cluster_centers = []
        attempts = 0
        while len(cluster_centers) < n_clusters and attempts < 100:
            cx = np.random.randint(1, width - 1)
            cy = np.random.randint(1, height - 1)
            dist_from_nest = abs(cx - nest_cx) + abs(cy - nest_cy)
            if dist_from_nest >= min_dist_from_nest:
                cluster_centers.append((cx, cy))
            attempts += 1
        
        # If we couldn't find enough valid centers, fill with any valid position
        while len(cluster_centers) < n_clusters:
            cluster_centers.append((np.random.randint(1, width - 1), np.random.randint(1, height - 1)))
        
        # Place food items around each cluster center
        food_per_cluster = N_food // n_clusters
        for cx, cy in cluster_centers:
            placed = 0
            cluster_attempts = 0
            while placed < food_per_cluster and cluster_attempts < 50:
                fx = cx + np.random.randint(-cluster_radius, cluster_radius + 1)
                fy = cy + np.random.randint(-cluster_radius, cluster_radius + 1)
                if 0 <= fx < width and 0 <= fy < height and (fx, fy) not in self.foods:
                    self.foods.add((fx, fy))
                    placed += 1
                cluster_attempts += 1
        
        # Fill any remaining slots with random positions (rounding residual)
        while len(self.foods) < N_food:
            new_food_pos = (np.random.randint(width), np.random.randint(height))
            self.foods.add(new_food_pos)

        self.step_count = 0
        self.metrics = {
            "food_collected": 0,
            "total_api_calls": 0,
            "avg_response_time": 0,
            "food_collected_by_llm": 0,
            "food_collected_by_rule": 0,
            "ants_carrying_food": 0,
            "ants_caught": 0,
            "llm_ants_caught": 0,
            "rule_ants_caught": 0,
            "predator_api_calls": 0  
        }
        self.with_queen = with_queen
        self.use_llm_queen = use_llm_queen
        self.selected_model = selected_model_param
        self.prompt_style = prompt_style_param

        # Pheromone system initialization
        self.pheromone_map = {
            'trail': np.zeros((width, height)),
            'alarm': np.zeros((width, height)),
            'recruitment': np.zeros((width, height)),
            'fear': np.zeros((width, height)) # Added fear pheromone
        }
        self.pheromone_decay_rate = 0.05  # 5% decay per step
        self.trail_deposit = 1.0
        self.alarm_deposit = 2.0
        self.recruitment_deposit = 1.5
        self.max_pheromone_value = 10.0
        self.fear_deposit = 3.0 # Fear pheromone deposit amount

        # Foraging efficiency grid
        self.foraging_efficiency_grid = np.zeros((width, height))
        self.foraging_decay_rate = 0.98  # 98% retention per step
        self.food_collection_score_boost = 10.0
        self.traverse_score_boost = 0.1

        # Initialize other properties
        self.queen_llm_anomaly_rep = "Queen's report will appear here when queen is active"
        self.food_depletion_history = []
        self.initial_food_count = N_food

        # Initialize blockchain logs
        self.blockchain_logs = []
        self.blockchain_transactions = []  # Structured transaction data
        self.enable_blockchain = True  # Always enabled
        self.food_collection_count = 0  # Debug counter
        
        # Add test blockchain log
        test_tx = f"0x{hash('test_init') % (2**64):016x}"
        self.blockchain_logs.append(f"Blockchain integration initialized. Test Tx: {test_tx}")
        print(f"[BLOCKCHAIN] Initialized with test transaction: {test_tx}")

        # Initialize IO client with safety checks
        self.api_enabled = False
        if IO_API_KEY:
            try:
                self.io_client = create_llm_client(
                    api_key=IO_API_KEY,
                    api_base=LITELLM_API_BASE
                )
                self.api_enabled = True
                self.log_error("LLM API initialized successfully.")
            except Exception as e:
                self.io_client = None
                self.log_error(f"Failed to initialize LLM API: {str(e)}")
        else:
            self.io_client = None
            self.log_error("IO_SECRET_KEY not found. LLM features disabled.")

        # Create agents based on type
        self.ants = []
        if agent_type == "LLM-Powered":
            self.ants = [SimpleAntAgent(i, self, True) for i in range(N_ants)]
        elif agent_type == "Rule-Based":
            self.ants = [SimpleAntAgent(i, self, False) for i in range(N_ants)]
        else:  # Hybrid
            for i in range(N_ants):
                is_llm = i < N_ants // 2
                self.ants.append(SimpleAntAgent(i, self, is_llm))

        # Create predators based on type
        self.predators = []
        if N_predators > 0:
            if predator_type == "LLM-Powered":
                self.predators = [PredatorAgent(i + 1000, self, True) for i in range(N_predators)]
            elif predator_type == "Rule-Based":
                self.predators = [PredatorAgent(i + 1000, self, False) for i in range(N_predators)]
            else:  # Hybrid
                for i in range(N_predators):
                    is_llm = i < N_predators // 2
                    self.predators.append(PredatorAgent(i + 1000, self, is_llm))

        self.queen = QueenAnt(self, use_llm=self.use_llm_queen) if self.with_queen else None
        # Queen initialization completed
        
        # Initialize queen report
        if self.queen:
            self.queen_llm_anomaly_rep = f"Queen initialized ({'LLM-Powered' if self.use_llm_queen else 'Heuristic'} guidance mode)"
        else:
            self.queen_llm_anomaly_rep = "No queen active"

    def step(self):
        self.step_count += 1
        guidance = {}
        
        if self.queen:
            try:
                # Queen provides guidance to ants
                guidance = self.queen.guide(self.selected_model)
            except Exception as e:
                self.log_error(f"Queen guidance failed: {str(e)}")
                guidance = {}

        self.metrics["ants_carrying_food"] = 0
        food_collected_this_step = 0
        for ant in self.ants:
            guided_pos = guidance.get(ant.unique_id)
            ant.step(guided_pos)
            if ant.carrying_food:
                self.metrics["ants_carrying_food"] += 1
            if ant.is_llm_controlled:
                self.metrics["total_api_calls"] += ant.api_calls
                ant.api_calls = 0

        # Step predators
        for predator in self.predators:
            predator.step()
            if predator.is_llm_controlled:
                self.metrics["predator_api_calls"] += predator.api_calls
                self.metrics["total_api_calls"] += predator.api_calls  # Also add to total
                predator.api_calls = 0

        # Update foraging efficiency grid
        self.foraging_efficiency_grid *= self.foraging_decay_rate
        self.foraging_efficiency_grid[self.foraging_efficiency_grid < 0.01] = 0

        # Add score for LLM ant traversals
        for ant in self.ants:
            if ant.is_llm_controlled:
                x, y = ant.pos
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.foraging_efficiency_grid[x, y] += self.traverse_score_boost

        # Apply pheromone evaporation
        for p_type in self.pheromone_map:
            self.pheromone_map[p_type] *= (1 - self.pheromone_decay_rate)
            self.pheromone_map[p_type] = np.clip(self.pheromone_map[p_type], 0, self.max_pheromone_value)

        # Track food depletion
        food_piles_remaining = len(self.foods)
        self.food_depletion_history.append({
            "step": self.step_count,
            "food_piles_remaining": food_piles_remaining
        })

        # Debug output for blockchain
        if self.step_count % 5 == 0:  # Every 5 steps
            pass  # Step completed

    def get_neighborhood(self, x, y):
        neigh = [(x+dx, y+dy)
                 for dx in (-1,0,1)
                 for dy in (-1,0,1)
                 if (dx,dy)!=(0,0)]
        valid_neigh = []
        for i,j in neigh:
            if 0 <= i < self.width and 0 <= j < self.height:
                valid_neigh.append((i,j))
        return valid_neigh

    def is_food_at(self, pos):
        return pos in self.foods

    def collect_food(self, pos, is_llm_controlled_ant):
        """Enhanced food collection with efficiency tracking and blockchain logging"""
        if pos in self.foods:
            self.foods.discard(pos)
            self.metrics["food_collected"] += 1
            self.food_collection_count += 1  # Debug counter

            if is_llm_controlled_ant:
                self.metrics["food_collected_by_llm"] += 1
            else:
                self.metrics["food_collected_by_rule"] += 1

            # Update foraging efficiency grid
            x, y = pos
            if 0 <= x < self.width and 0 <= y < self.height:
                if is_llm_controlled_ant:
                    self.foraging_efficiency_grid[x, y] += self.food_collection_score_boost

            # Collecting food at position

            # --- Blockchain Integration: Record food collection on-chain ---
            try:
                import time
                submit_time = time.time() * 1000  # milliseconds
                tx_hash = None
                latency_ms = 0
                success = False
                gas_used = 0
                
                # Try to submit real blockchain transaction
                try:
                    from blockchain.client import w3, acct, memory_contract, MEMORY_CONTRACT_ADDRESS
                    
                    # Detailed debugging
                    # Blockchain connection verified
                    
                    if not memory_contract:
                        raise Exception("memory_contract is None - contract not initialized")
                    if not MEMORY_CONTRACT_ADDRESS:
                        raise Exception("MEMORY_CONTRACT_ADDRESS is None - check .env file")
                    if not w3.is_connected():
                        raise Exception("Web3 not connected to RPC")
                    
                    # All checks passed, submit real transaction
                    food_id = self.food_collection_count
                    x_coord, y_coord = pos
                    
                    # Submitting blockchain transaction
                    
                    # Get nonce - use 'pending' to include pending transactions
                    nonce = w3.eth.get_transaction_count(acct.address, 'pending')
                    
                    # Get current gas price and add 10% buffer to avoid underpricing
                    base_gas_price = w3.eth.gas_price
                    gas_price = int(base_gas_price * 1.1)
                    
                    tx = memory_contract.functions.recordFood(
                        food_id, x_coord, y_coord
                    ).build_transaction({
                        'from': acct.address,
                        'nonce': nonce,
                        'gas': 100000,  # Estimated gas limit
                        'gasPrice': gas_price,
                        'chainId': w3.eth.chain_id
                    })
                    
                    # Sign and send transaction
                    signed_tx = acct.sign_transaction(tx)
                    # Use raw_transaction (snake_case) for newer web3.py versions
                    raw_tx = signed_tx.raw_transaction if hasattr(signed_tx, 'raw_transaction') else signed_tx.rawTransaction
                    tx_hash_bytes = w3.eth.send_raw_transaction(raw_tx)
                    tx_hash = tx_hash_bytes.hex()
                    if not tx_hash.startswith('0x'):
                        tx_hash = '0x' + tx_hash
                    
                    # Wait for confirmation with extended timeout
                    receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=60)
                    confirm_time = time.time() * 1000
                    latency_ms = int(confirm_time - submit_time)
                    success = receipt['status'] == 1
                    gas_used = receipt['gasUsed']
                    
                    # Add delay between transactions to prevent nonce conflicts
                    time.sleep(1.5)
                    
                except Exception as blockchain_error:
                    # Fall back to simulated transaction
                    print(f"[BLOCKCHAIN] ⚠️ Real blockchain unavailable: {blockchain_error}")
                    print(f"[BLOCKCHAIN] Error type: {type(blockchain_error).__name__}")
                    import traceback
                    print(f"[BLOCKCHAIN] Traceback: {traceback.format_exc()}")
                    print("[BLOCKCHAIN] ⚠️ Using simulated transaction as fallback")
                    tx_hash = f"0x{hash(f'{pos}_{self.step_count}_{time.time()}') % (16**64):064x}"
                    latency_ms = np.random.randint(50, 200)
                    confirm_time = submit_time + latency_ms
                    success = True
                
                # Store structured transaction data
                tx_data = {
                    'tx_hash': tx_hash,
                    'step': self.step_count,
                    'position': list(pos),
                    'ant_type': 'LLM' if is_llm_controlled_ant else 'Rule',
                    'submit_time': submit_time,
                    'confirm_time': submit_time + latency_ms,
                    'latency_ms': latency_ms,
                    'success': success,
                    'gas_used': gas_used
                }
                self.blockchain_transactions.append(tx_data)
                
                log_message = f"Food collected at position {pos} by {'LLM' if is_llm_controlled_ant else 'Rule'}-based ant. Tx: {tx_hash} (latency: {latency_ms}ms)"
                self.blockchain_logs.append(log_message)
                print(f"[BLOCKCHAIN] {log_message}")
                    
            except Exception as b_e:
                error_msg = f"Blockchain log failed for food collection at {pos}: {b_e}"
                self.blockchain_logs.append(error_msg)
                print(f"[BLOCKCHAIN ERROR] {error_msg}")
                # Don't let blockchain errors break the simulation

    def place_food(self, pos):
        if pos not in self.foods:
            self.foods.add(pos)

    def get_agent_positions(self):
        return [ant.pos for ant in self.ants]

    def get_food_positions(self):
        return list(self.foods)

    def deposit_pheromone(self, pos, p_type, amount):
        """Deposits pheromone at a given position"""
        if 0 <= pos[0] < self.width and 0 <= pos[1] < self.height:
            self.pheromone_map[p_type][pos[0], pos[1]] += amount
            self.pheromone_map[p_type][pos[0], pos[1]] = min(
                self.pheromone_map[p_type][pos[0], pos[1]], 
                self.max_pheromone_value
            )

    def get_local_pheromones(self, pos, radius):
        """Returns local pheromone levels around a position"""
        x, y = pos
        local_trail = 0.0
        local_alarm = 0.0
        local_recruitment = 0.0
        local_fear = 0.0 # Added fear pheromone

        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    local_trail += self.pheromone_map['trail'][nx, ny]
                    local_alarm += self.pheromone_map['alarm'][nx, ny]
                    local_recruitment += self.pheromone_map['recruitment'][nx, ny]
                    local_fear += self.pheromone_map['fear'][nx, ny] # Added fear pheromone
        
        # Normalize by area
        area = (2 * radius + 1)**2
        return {
            'trail': local_trail / area,
            'alarm': local_alarm / area,
            'recruitment': local_recruitment / area,
            'fear': local_fear / area # Added fear pheromone
        }

    def set_pheromone_params(self, decay_rate, trail_deposit=None, alarm_deposit=None, recruitment_deposit=None, max_value=None, fear_deposit=None):
        """Update pheromone parameters during runtime."""
        self.pheromone_decay_rate = decay_rate
        if trail_deposit is not None:
            self.trail_deposit = trail_deposit
        if alarm_deposit is not None:
            self.alarm_deposit = alarm_deposit
        if recruitment_deposit is not None:
            self.recruitment_deposit = recruitment_deposit
        if max_value is not None:
            self.max_pheromone_value = max_value
        if fear_deposit is not None:
            self.fear_deposit = fear_deposit

    def log_error(self, message: str):
        """Log a non-fatal error during the simulation."""
        self.errors.append(message)
        print(f"[SIMULATION] {message}")  # Also print for debugging