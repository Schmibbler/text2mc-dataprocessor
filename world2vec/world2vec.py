import anvil
import os
from typing import Generator
import mcschematic
from typing import List

# Now you can use mcschematic

# Class to parse data files and vectorize them into information the model can train on
class World2Vec:

    # Converts old blocks to new ones
    @staticmethod
    def convert_if_old(block) -> anvil.Block:
        if isinstance(block, anvil.OldBlock):
            try:
                block = anvil.OldBlock.convert(block)
            except:
                return None
        return block

    # Reads all region files in dir and returns a Generator of Chunks, all of which contain blocks that are not in natural_blocks.txt
    def get_build_chunks(dir: str) -> tuple[list, bool]:
        print("Searching directory " + dir + "...")
        # Read in the natural blocks to an array
        nb_file = open("natural_blocks.txt", 'r')
        natural_blocks = nb_file.read().splitlines()
        nb_file.close()
        # This is the list of all the build chunks
        build_chunks = []
        # This variable tracks the coordinates of the last identified build chunk, used to reduce computation time 
        # when faraway chunks are reached
        last_build_chunk = [None, None]
        # Dynamic radii to eliminate chunks that are too far from the build
        x_radius = 3
        z_radius = 3
        # Variables to track the build bounds
        low_x = None
        high_x = None
        low_z = None
        high_z = None
        # Flag for superflat worlds
        superflat = None
        # Iterate through .mca files in dir
        for filename in os.listdir(dir):
            if filename.endswith(".mca"):
                # Retrieve the region
                region = anvil.Region.from_file(os.path.join(dir, filename))
                # Only search the region file if it is not empty (because apparently sometimes they are empty?)
                if (region.data):
                    # Set search sections
                    search_sections = range(3, 10)
                    # Retrieve each chunk in the region
                    for x in range(0, 32):
                        for z in range(0, 32):
                            # Region files need not contain 32x32 chunks, so we must check if the chunk exists
                            if region.chunk_data(x, z):
                                chunk = anvil.Region.get_chunk(region, x, z)
                                # Check whether the given world is superflat
                                if superflat is None:
                                    start_section = 0
                                    if chunk.version is not None and chunk.version > 1451:
                                        start_section = -4
                                    section = anvil.Chunk.get_section(chunk, start_section)
                                    for block in anvil.Chunk.stream_blocks(chunk, section = section):
                                        block = World2Vec.convert_if_old(block)
                                        if block != None and anvil.Block.name(block) == "minecraft:grass_block":
                                            superflat = True
                                            break
                                    if superflat is None:
                                        superflat = False
                                # If it's a superflat world, change the search sections
                                if superflat:
                                    if chunk.version is not None and chunk.version > 1451:
                                        search_sections = range(-4, 4)
                                    else:
                                        search_sections = range(0, 8)
                                # If there is already an identified build chunk
                                if last_build_chunk[0] != None:
                                    # If this chunk is too far away, just skip it
                                    if (abs(chunk.x - last_build_chunk[0]) >= x_radius) and (abs(chunk.z - last_build_chunk[1]) >= z_radius):
                                        continue
                                # Search the relevant sections
                                chunk_added = False
                                for s in search_sections:
                                    section = anvil.Chunk.get_section(chunk, s)
                                    # Check each block in the section
                                    for block in anvil.Chunk.stream_blocks(chunk, section=section):
                                        block = World2Vec.convert_if_old(block)
                                        # If it's not a natural block, add this chunk to the Generator
                                        if block != None and anvil.Block.name(block) not in natural_blocks:
                                            build_chunks.append(chunk)
                                            if low_x is None or chunk.x < low_x:
                                                low_x = chunk.x
                                            if high_x is None or chunk.x > high_x:
                                                high_x = chunk.x
                                            if low_z is None or chunk.z < low_z:
                                                low_z = chunk.z
                                            if high_z is None or chunk.z > high_z:
                                                high_z = chunk.z
                                            if last_build_chunk[0] != None:
                                                x_radius = x_radius + abs(chunk.x - last_build_chunk[0])
                                                z_radius = z_radius + abs(chunk.z - last_build_chunk[1])
                                            last_build_chunk[0] = chunk.x
                                            last_build_chunk[1] = chunk.z
                                            chunk_added = True
                                            break
                                    if chunk_added:
                                        break
        # Iterate through .mca files in dir to fill in missing chunks
        for filename in os.listdir(dir):
            if filename.endswith(".mca"):
                # Retrieve the region
                region = anvil.Region.from_file(os.path.join(dir, filename))
                # Only search the region file if it is not empty (because apparently sometimes they are empty?)
                if (region.data):
                    # Retrieve each chunk in the region
                    for x in range(0, 32):
                        for z in range(0, 32):
                            # Region files need not contain 32x32 chunks, so we must check if the chunk exists
                            if region.chunk_data(x, z):
                                chunk = anvil.Region.get_chunk(region, x, z)
                                if chunk not in build_chunks:
                                    if (chunk.x >= low_x and chunk.x <= high_x) and (chunk.z >= low_z and chunk.z <= high_z):
                                        build_chunks.append(chunk)
        # Check for failure and send error message
        if last_build_chunk[0] == None:
            print("Error: Build could not be found in region files")
            return
        print("Build chunks found!")
        return build_chunks, superflat

    # Extracts a build from a list of chunks and writes a file containing block info and coordinates
    def extract_build(chunks: List, superflat: bool, build_no: int):
        print("Extracting build from chunks into " + "my_schematics" + ".schematic...")
        # Open the output file
        schem = mcschematic.MCSchematic()
        # Part of this process is finding the lowest y-value that can be considered the "surface"
        # This will almost certainly never by y=-100, so if this value is unchanged, we know something went wrong
        lowest_surface_y = 0
        # Iterate through the chunks
        min_range = 0
        level = 0
        # If it's a superflat world, we need to search the lower sections
        if(superflat):
            min_range = -4
            lowest_surface_y = -100
            level = -100
        for chunk in chunks:
            surface_section = None
            surface_section_y = 0
            # Begin with section -4 or 0 depending on world surface and find the first section up from there that contains a large amount of air (the "surface" section)
            # We stop at section 10 because that is the highest section that get_build_chunks() searches
            for s in range(min_range, 10):
                air_count = 0
                section = anvil.Chunk.get_section(chunk, s)
                for block in anvil.Chunk.stream_blocks(chunk, section=section):
                    block = World2Vec.convert_if_old(block)
                    if block != None and anvil.Block.name(block) == "minecraft:air":
                        air_count += 1
                        # We'll check for a section to have a good portion of air, testing says 1024 blocks is a good fit
                        if air_count == 1024:
                            surface_section = section
                            surface_section_y = s
                            break
                # If we've already found a surface section, stop searching
                if surface_section != None:
                    break
            # Check for failure and output an error message
            if surface_section is None:
                print("Error: No surface section found in chunk", chunk.x, chunk.z)
                return
            # Iterate through the surface section and find the lowest surface block
            # Because we are specifying the section, we are using relative coordinates in the 0-16 range, rather than global coordinates 
            # (this is better for us, as it is world-agnostic)
            for x in range(0, 16):
                for z in range(0, 16):
                    for y in range(0, 16):
                        # Here we calculate the true y value, in order to compare against other sections
                        true_y = y + (surface_section_y * 16)
                        block = World2Vec.convert_if_old(anvil.Chunk.get_block(chunk, x, y, z, section=surface_section))
                        # Check if there is an air block above it, to confirm it is a surface block
                        if block != None and anvil.Block.name(anvil.Chunk.get_block(chunk, x, true_y + 1, z)) == "minecraft:air":
                            if lowest_surface_y == level or true_y < lowest_surface_y:
                                lowest_surface_y = true_y
        # Check for failure and output an error message
        if lowest_surface_y == level:
            print("Error: No surface block found in chunks")
            return
        # Again, we don't need global coordinates, but we do need the blocks to be in the right places relative to each other
        # So, we're going to "create" our own (0, 0) and place everything relative to that point
        # To do this, we're just going to pick one of the chunks and call it the (0, 0) chunk, then map all the other chunks accordingly
        origin_x = chunks[0].x
        origin_z = chunks[0].z
        # Additionally, we are going to find blocks layer by layer, so we need to keep track of which y we are searching, starting with the value we found earlier
        current_y = lowest_surface_y
        # We also need a stopping point, so we need a flag to tell us when to stop searching for blocks (we don't want to spend time searching the sky)
        searching = True
        while (searching):
            empty_layer = True
            for chunk in chunks:
                relative_chunk_x = chunk.x - origin_x
                relative_chunk_z = chunk.z - origin_z
                for x in range(0, 16):
                    for z in range(0, 16):
                        # This function CAN take global y values, so we don't have to worry about finding specific sections
                        block = World2Vec.convert_if_old(anvil.Chunk.get_block(chunk, x, current_y, z))
                        # We're going to ignore air blocks, as we can just fill in empty coordinates later with air blocks
                        # This just cleans up the output file for better readability
                        if block != None and anvil.Block.name(block) != "minecraft:air":
                            # We've found a non-air block, so this isn't an empty layer
                            empty_layer = False
                            # We need to map the coordinates to our new system now
                            new_x = (relative_chunk_x * 16) + x
                            new_y = current_y - lowest_surface_y
                            new_z = (relative_chunk_z * 16) + z
                            # Extract and format the block's properties (if they exist)
                            block_properties = "["
                            if len(block.properties) > 0:
                                for prop in sorted(block.properties):
                                    block_properties = block_properties + prop + "=" + str(block.properties.get(prop)) + ","
                            block_properties = block_properties[:-1] + "]"
                            # Finally, we write to the output file
                            if len(block.properties) > 0:
                                schem.setBlock((int(new_x), int(new_y), int(new_z)),anvil.Block.name(block) + block_properties)
                            else:
                                schem.setBlock((int(new_x), int(new_y), int(new_z)),anvil.Block.name(block))
            # If this layer is empty, stop searching
            if (empty_layer):
                searching = False
            # Otherwise, increase to the next y layer
            else:
                current_y += 1
        # Get the current directory of the Python script
        current_directory = os.path.dirname(__file__)

        # Extract path of code file, and add to with testbuilds
        folder_name = 'testbuilds'
        folder_path = os.path.join(current_directory, folder_name)

        # Check if the folder exists
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            # Create the folder if it doesn't exist
            os.makedirs(folder_path)
            
        # Now that the folder exists, you can save the schematic file
        schem.save(folder_path, "my_schematic_" + str(build_no), mcschematic.Version.JE_1_20_1)

        print("Build extracted to " + "my_schematics" + str(build_no) + ".schematic...!\n")