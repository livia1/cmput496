'''
CURRENT PLAN:
make sure state_win_command is appended once. get current stone color and
print it in a winning message. Gen move will use solve and pick a good
move.
'''

"""
Module for playing games of Go using GoTextProtocol

This code is based off of the gtp module in the Deep-Go project
by Isaac Henrion and Amos Storkey at the University of Edinburgh.
"""
import traceback
import sys
import os
import time, threading
from board import GoBoard
from board_util import GoBoardUtil, BLACK, WHITE, EMPTY, BORDER, FLOODFILL
import numpy as np
import re
#Modded BW Code
import copy 

class GtpConnection():

	def __init__(self, go_engine, debug_mode = False):
		"""
		Hello, this is Brett.
		object that plays Go using GTP

		Parameters
		----------
		go_engine: GoPlayer
			a program that is capable of playing go by reading GTP commands
		debug_mode: prints debug messages
		"""
		self.stdout = sys.stdout
		sys.stdout = self
		self._debug_mode = debug_mode
		self.go_engine = go_engine
		self.komi = 0
		self.timelimit = 1
		self.board = GoBoard(7)
		self.commands = {
			"protocol_version": self.protocol_version_cmd,
			"quit": self.quit_cmd,
			"name": self.name_cmd,
			"boardsize": self.boardsize_cmd,
			"showboard": self.showboard_cmd,
			"clear_board": self.clear_board_cmd,
			"komi": self.komi_cmd,
			"version": self.version_cmd,
			"known_command": self.known_command_cmd,
			"set_free_handicap": self.set_free_handicap,
			"genmove": self.genmove_cmd,
			"list_commands": self.list_commands_cmd,
			"play": self.play_cmd,
			"final_score": self.final_score_cmd,
			"legal_moves": self.legal_moves_cmd,
			"timelimit": self.timelimit_cmd,
			"solve": self.solve_cmd,
			"undolast": self.undo_last_cmd,
			"test": self.testingstuff_cmd
		}

		# used for argument checking
		# values: (required number or arguments, error message on argnum failure)
		self.argmap = {
			"boardsize": (1, 'Usage: boardsize INT'),
			"komi": (1, 'Usage: komi FLOAT'),
			"known_command": (1, 'Usage: known_command CMD_NAME'),
			"set_free_handicap": (1, 'Usage: set_free_handicap MOVE (e.g. A4)'),
			"genmove": (1, 'Usage: genmove {w, b}'),
			"play": (2, 'Usage: play {b, w} MOVE'),
			"legal_moves": (1, 'Usage: legal_moves {w, b}'), "timelimit": (1, "Usage: timelimit INT")

		}
		# Modded BW Code
		self.last_state = GoBoard(7)
		self.state_counter = 0
		self.played_states = []
		self.does_black_win = False 
		self.black_win_state = []
		self.state_commands = []
		self.state_win_commands = []
		self.total_counter = 0
		self.dont_double = False
		self.negamax_count = 0
		self.solve_move_pick = []
		self.played_counter = 0
	
	def __del__(self):
		sys.stdout = self.stdout

	def write(self, data):
		self.stdout.write(data)

	def flush(self):
		self.stdout.flush()

	def start_connection(self):
		"""
		start a GTP connection. This function is what continuously monitors
		the user's input of commands.
		"""
		self.debug_msg("Start up successful...\n\n")
		line = sys.stdin.readline()
		while line:
			self.get_cmd(line)
			line = sys.stdin.readline()

	def get_cmd(self, command):
		"""
		parse the command and execute it

		Arguments
		---------
		command : str
			the raw command to parse/execute
		"""
		if len(command.strip(' \r\t')) == 0:
			return
		if command[0] == '#':
			return
		# Strip leading numbers from regression tests
		if command[0].isdigit():
			command = re.sub("^\d+", "", command).lstrip()

		elements = command.split()
		if not elements:
			return
		command_name = elements[0]; args = elements[1:]
		
		if command_name == "play" and self.argmap[command_name][0] != len(args):
			self.respond('illegal move: {} wrong number of arguments'.format(args[0]))
			return

		if self.arg_error(command_name, len(args)):
			return
		if command_name in self.commands:
			try:
				self.commands[command_name](args)
			except Exception as e:
				self.debug_msg("Error executing command {}\n".format(str(e)))
				self.debug_msg("Stack Trace:\n{}\n".format(traceback.format_exc()))
				raise e
		else:
			self.debug_msg("Unknown command: {}\n".format(command_name))
			self.error('Unknown command')
			sys.stdout.flush()
		
	def arg_error(self, cmd, argnum):
		"""
		checker funciton for the number of arguments given to a command

		Arguments
		---------
		cmd : str
			the command name
		argnum : int
			number of parsed argument

		Returns
		-------
		True if there was an argument error
		False otherwise
		"""
		if cmd in self.argmap and self.argmap[cmd][0] > argnum:
			self.error(self.argmap[cmd][1])
			return True
		return False

	def debug_msg(self, msg = ''):
		""" Write a msg to the debug stream """
		if self._debug_mode:
			sys.stderr.write(msg); sys.stderr.flush()

	def error(self, error_msg = ''):
		""" Send error msg to stdout and through the GTP connection. """
		sys.stdout.write('? {}\n\n'.format(error_msg)); sys.stdout.flush()

	def respond(self, response = ''):
		""" Send msg to stdout """
		sys.stdout.write('= {}\n\n'.format(response)); sys.stdout.flush()

	def reset(self, size):
		"""
		Resets the state of the GTP to a starting board

		Arguments
		---------
		size : int
			the boardsize to reinitialize the state to
		"""
		self.board.reset(size)

	def protocol_version_cmd(self, args):
		""" Return the GTP protocol version being used (always 2) """
		self.respond('2')

	def quit_cmd(self, args):
		""" Quit game and exit the GTP interface """
		self.respond()
		exit()

	def name_cmd(self, args):
		""" Return the name of the player """
		self.respond(self.go_engine.name)

	def version_cmd(self, args):
		""" Return the version of the player """
		self.respond(self.go_engine.version)

	def clear_board_cmd(self, args):
		""" clear the board """
		self.state_counter = 0
		self.played_states = []
		self.does_black_win = False 
		self.black_win_state = []
		self.state_commands = []
		self.state_win_commands = []
		self.total_counter = 0
		self.dont_double = False
		self.reset(self.board.size)
		self.respond()

	def boardsize_cmd(self, args):
		"""
		Reset the game and initialize with a new boardsize

		Arguments
		---------
		args[0] : int
			size of reinitialized board
		"""
		self.reset(int(args[0]))
		self.respond()

	def showboard_cmd(self, args):
		self.respond('\n' + str(self.board.get_twoD_board()))

	def komi_cmd(self, args):
		"""
		Set the komi for the game

		Arguments
		---------
		args[0] : float
			komi value
		"""
		self.komi = float(args[0])
		self.respond()

	def known_command_cmd(self, args):
		"""
		Check if a command is known to the GTP interface

		Arguments
		---------
		args[0] : str
			the command name to check for
		"""
		if args[0] in self.commands:
			self.respond("true")
		else:
			self.respond("false")

	def list_commands_cmd(self, args):
		""" list all supported GTP commands """
		self.respond(' '.join(list(self.commands.keys())))

	def set_free_handicap(self, args):
		"""
		clear the board and set free handicap for the game

		Arguments
		---------
		args[0] : str
			the move to handicap (e.g. B2)
		"""
		self.board.reset(self.board.size)
		for point in args:
			move = GoBoardUtil.move_to_coord(point, self.board.size)
			point = self.board._coord_to_point(*move)
			if not self.board.move(point, BLACK):
				self.debug_msg("Illegal Move: {}\nBoard:\n{}\n".format(move, str(self.board.get_twoD_board())))
		self.respond()

	def legal_moves_cmd(self, args):
		"""
		list legal moves for the given color
		Arguments
		---------
		args[0] : {'b','w'}
			the color to play the move as
			it gets converted to  Black --> 1 White --> 2
			color : {0,1}
			board_color : {'b','w'}
		"""
		try:
			board_color = args[0].lower()
			color = GoBoardUtil.color_to_int(board_color)
			moves = GoBoardUtil.generate_legal_moves(self.board, color)
			self.respond(moves)
		except Exception as e:
			self.respond('Error: {}'.format(str(e)))		

	def undo_last_cmd(self, args):
		"""
		BW Code:
		Changes board to last move,
		Makes the last board the undone one
		Makes use of deep copy
		"""
		"""temp_board = copy.deepcopy(self.board)
		self.board = copy.deepcopy(self.last_state)
		self.last_state = copy.deepcopy(temp_board)"""
		if len(self.played_states) > 0: 
			self.board = copy.deepcopy(self.played_states[-1])
			self.played_states.pop(-1)
			#self.respond("Last State")
			#self.showboard_cmd(self)
		else:
			self.respond("No previous states")
		#if len(self.state_commands) > 0:
			#self.state_commands.pop(-1)

	def play_cmd(self, args, other = 0):
		"""
		play a move as the given color

		Arguments
		---------
		args[0] : {'b','w'}
			the color to play the move as
			it gets converted to  Black --> 1 White --> 2
			color : {0,1}
			board_color : {'b','w'}
		args[1] : str
			the move to play (e.g. A5)
		"""
		try:
			board_color = args[0].lower()
			board_move = args[1]
			color = GoBoardUtil.color_to_int(board_color)
			move = GoBoardUtil.move_to_coord(args[1], self.board.size)
			if move:
				self.played_states.append(copy.deepcopy(self.board))
				self.total_counter += 1
				move = self.board._coord_to_point(move[0], move[1])
			else:
				return
			if not self.board.move(move, color):
				return
			if other == 0:
				self.respond()
				self.played_counter += 1
		except Exception as e:
			if other == 0:
				self.respond("illegal move: {} {} {}".format(board_color, board_move, str(e)))
			self.played_states.pop(-1)
			self.state_commands.pop(-1)
		self.showboard_cmd(self)

	def final_score_cmd(self, args):
		self.respond(self.board.final_score(self.komi)) 
	
	def genmove_cmd(self, args):
		"""
		generate a move for the specified color

		Arguments
		---------
		args[0] : {'b','w'}
			the color to generate a move for
			it gets converted to  Black --> 1 White --> 2
			color : {0,1}
			board_color : {'b','w'}
		"""
		try:
			start = time.process_time()
			board_color = args[0].lower()
			color = GoBoardUtil.color_to_int(board_color)
			'''
			We have the stone color and the board state at this point.
			
			PLAN: We look recursively through the board states. When we
			find a winning state, we return the first move.
			
			PROBLEM: We have no heuristic to determine if that move is
			actually a winning move. ie, the second player could play
			an optimal move that may divert from the winning state we
			found.
			
			IDEA: When we find a winning state, we take the first move
			that lead to that, then we "make" that move for the second
			player and see if their first winning move leads to the
			same state, if it does, then there is a better chance the
			first move we made will be an optimal move
			'''
			move = self.solve_cmd(self.board)
			if move != None:
				splitColor, splitMove = move.split(" ")
				self.commands["play"]([splitColor, splitMove], 5)

			elif (stoptime > self.timelimit):
				move = self.go_engine.get_move(self.board, color)
				
			elif move is None:
				self.respond("Resign")
				return
			
			if not self.board.check_legal(move, color):
				move = self.board._point_to_coord(move)
				board_move = GoBoardUtil.format_point(move)
				raise RuntimeError("Illegal move given by engine")

			# move is legal; play it
			self.board.move(move, color)
			self.debug_msg("Move: {}\nBoard: \n{}\n".format(move, str(self.board.get_twoD_board())))
			move = self.board._point_to_coord(move)
			board_move = GoBoardUtil.format_point(move)
			self.respond(board_move)
		except Exception as e:
			self.respond('Error: {}'.format(str(e)))
			
	def timelimit_cmd(self, args):
		print ("reached time limit command")
		if int(args[0]) >= 1 and int(args[0]) <= 100:
			self.timelimit = int(args[0])
			self.respond()
		else:
			self.respond('Error: {} is not a valid timelimit'.format(int(args[0])))

			
	def negamaxBoolean(self, board, Time, score):
		'''
		IDEA: We use DFS to go through the tree. When we reach a terminal
		      node, we score it as a -1, so that it will return a score
			  of 1 to the player who made the last move, which means the
			  last player to move will get a score of 1.
			  self.state_commands = []
		      self.state_win_commands = []
	    '''
		timePassed = (time.process_time() - Time)
		self.board = board
		
		super_success = False
		if len(GoBoardUtil.generate_legal_moves(self.board, self.board.to_play)) == 0:
			# We return -1 because this player has no more moves and lossed.
			self.state_win_commands.append(copy.deepcopy(self.state_commands))
			return -1
			#return (self.isSuccess(self.board), score)
		
		moves = GoBoardUtil.generate_legal_moves(self.board, self.board.to_play)
		moves = moves.split(" ")

		#ADDED CODE:
		best = -100

		while timePassed < self.timelimit:
			#count = 0
			for m in moves:
				self.negamax_count += 1
				#count = count + 1
				move_played = [GoBoardUtil.int_to_color(self.board.to_play), m]
				self.state_commands.append([GoBoardUtil.int_to_color(self.board.to_play), m])			
				self.commands["play"]([GoBoardUtil.int_to_color(self.board.to_play), m], 5)
				#print([GoBoardUtil.int_to_color(self.board.to_play), m])
				#self.state_commands.append([GoBoardUtil.int_to_color(self.board.to_play), m])
				#print(self.state_commands)
				
				#ADDED CODE:
				value = -self.negamaxBoolean(self.board, Time, score)
				if (value > best):
					print(best)
					best = value
					print("Made it")
					print(best)
					self.state_win_commands = copy.deepcopy(self.state_commands)
					if self.negamax_count == 1:
						self.solve_move_pick = copy.deepcopy(move_played)
				if self.negamax_count == 1:
					self.played_states.append(copy.deepcopy(self.board))
				self.negamax_count -= 1
				self.undo_last_cmd(self)

			return 1
		
		print("Times up Undoing all moves and exiting the negamaxboolean")
#		exit()
		
	def testingstuff_cmd(self, args):
		for x in range(len(self.state_win_commands)-1):
			print(self.state_win_commands[x])
		for x in range(len(self.black_win_state)-1):
			y = self.black_win_state[x]
			self.board = y
			self.showboard_cmd(self)
		
	def solve_cmd(self, args):
#		
		org_board = copy.deepcopy(self.board)
		t = time.process_time()
		try:
			win = self.negamaxBoolean(self.board, t, 0)
			self.board = org_board

			if win == 1:
				if self.played_counter%2 == 0:
					print("won")
					next_move = self.solve_move_pick[0]+ " " + self.solve_move_pick[1]
					self.respond(next_move)
							# Added BW code
					del self.state_win_commands[:]
					del self.state_commands[:]
					return (next_move)
				else:
					self.respond("b")
			elif win == -1:
				print("Lost")
			else:
				print("uuhh")

		# Added BW code
			del self.state_win_commands[:]
			del self.state_commands[:]
		except: 
			self.respond("Unknown")




