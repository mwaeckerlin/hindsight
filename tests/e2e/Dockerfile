# the test client: the image under test with the check script, so the checks
# run with the same Python and without anything installed on the host
FROM mwaeckerlin/hindsight
COPY check_hindsight.py /opt/hindsight-tests/
ENTRYPOINT ["/opt/hindsight/venv/bin/python", "/opt/hindsight-tests/check_hindsight.py"]
