import io, os
base = r"e:\trae\中文评论智能分析系统\backend\src\main\java\com\example\commentanalysis"
files = [
 "entity/AnalysisTask.java","entity/CommentData.java","entity/AnalysisResult.java",
 "entity/KeywordStatistics.java","entity/TaskStatistics.java","entity/SysUser.java",
 "common/ResultCode.java","common/Result.java","common/PageVO.java","common/GlobalExceptionHandler.java",
 "config/AuthInterceptor.java","config/WebMvcConfig.java","config/InferenceExecutorConfig.java","config/InferenceProperties.java","config/ModelProperties.java",
 "ai/TextPreprocessor.java","ai/KeywordExtractor.java","ai/KeywordAccumulator.java","ai/KeywordResult.java","ai/SentimentResult.java","ai/BertTokenizer.java",
 "mapper/CommentDataMapper.java","mapper/AnalysisResultMapper.java","mapper/AnalysisTaskMapper.java",
 "service/impl/ResultServiceImpl.java","service/impl/UserServiceImpl.java","scheduler/TaskRecoveryRunner.java",
 "vo/ProgressVO.java","vo/ResultVO.java","vo/SentimentStatisticsVO.java","vo/KeywordVO.java","vo/ModelInfoVO.java","vo/ParseReportVO.java"
]
for f in files:
    p = os.path.join(base, f.replace("/", os.sep))
    print("\n\n===== " + f + " =====")
    print(io.open(p, encoding="utf-8").read())
