pipeline = JRAPipeline(config)
try:
    rows = pipeline.run(
        race_urls=[
            "https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0107202601061120260329/50"
        ]
    )
    logging.info("Finished. Rows=%d output=%s state=%s", len(rows), config.output_csv, config.state_path)
finally:
    pipeline.close()