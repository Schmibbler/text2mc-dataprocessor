from world2vec import World2Vec

build_chunks, superflat = World2Vec.get_build_chunks("test_regions1")

World2Vec.extract_build(build_chunks, superflat, 1)