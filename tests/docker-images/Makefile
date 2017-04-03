base:
	docker build -t nathanhoad/gbulb-base -f base.Dockerfile .;
python:
	test ${VERSION}
	docker build -t nathanhoad/gbulb-python:${VERSION} -f python.Dockerfile --build-arg=PYTHON_VERSION=${VERSION} .;
