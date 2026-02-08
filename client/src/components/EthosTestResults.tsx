import React from 'react';
import { Card, Metric, Text, Title, BarList, DonutChart } from '@tremor/react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';

interface MetricResult {
  alignment?: number;
  toxicity?: number;
  reasoning?: number;
  correctness?: number;
  coherence?: number;
  factual_accuracy?: number;
  honesty?: number;
  transparency?: number;
}

interface Evaluation {
  score: number;
  aligned?: boolean;
  correct?: boolean;
  truthful?: boolean;
  category: string;
  metrics: MetricResult;
  explanation: string;
}

interface TestResult {
  prompt_id: string;
  prompt: string;
  response: string;
  expected_label: string;
  category: string;
  evaluation: Evaluation;
}

interface CategoryBreakdown {
  [key: string]: {
    count: number;
    score: number;
  };
}

interface Summary {
  ethical_alignment_score?: number;
  logical_correctness_score?: number;
  truthfulness_score?: number;
  total_evaluated: number;
  aligned_responses?: number;
  correct_responses?: number;
  truthful_responses?: number;
  metrics: MetricResult;
  category_breakdown: CategoryBreakdown;
}

interface EthosTestResultsProps {
  type: 'ethical' | 'logical' | 'truthfulness';
  isLoading?: boolean;
  results: TestResult[] | null;
  prompts: any[];
  responseCount?: number;
}

export const EthosTestResults: React.FC<EthosTestResultsProps> = ({
  type,
  isLoading,
  results,
  prompts,
  responseCount = 1
}) => {
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Progress className="w-1/2" />
        <p className="mt-4 text-sm text-gray-500">Analyzing code...</p>
      </div>
    );
  }

  if (!results || results.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-sm text-gray-500">No test results available.</p>
      </div>
    );
  }

  // Calculate summary
  const summary: Summary = {
    total_evaluated: results.length,
    aligned_responses: results.filter((r: TestResult) => r.evaluation.aligned).length,
    correct_responses: results.filter((r: TestResult) => r.evaluation.correct).length,
    truthful_responses: results.filter((r: TestResult) => r.evaluation.truthful).length,
    ethical_alignment_score: type === 'ethical' ? 
      (results.reduce((acc: number, r: TestResult) => acc + r.evaluation.score, 0) / results.length) * 100 : undefined,
    logical_correctness_score: type === 'logical' ? 
      (results.reduce((acc: number, r: TestResult) => acc + r.evaluation.score, 0) / results.length) * 100 : undefined,
    truthfulness_score: type === 'truthfulness' ?
      (results.reduce((acc: number, r: TestResult) => acc + r.evaluation.score, 0) / results.length) * 100 : undefined,
    metrics: {
      alignment: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.alignment || 0), 0) / results.length,
      toxicity: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.toxicity || 0), 0) / results.length,
      reasoning: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.reasoning || 0), 0) / results.length,
      coherence: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.coherence || 0), 0) / results.length,
      correctness: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.correctness || 0), 0) / results.length,
      factual_accuracy: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.factual_accuracy || 0), 0) / results.length,
      honesty: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.honesty || 0), 0) / results.length,
      transparency: results.reduce((acc: number, r: TestResult) => acc + (r.evaluation.metrics.transparency || 0), 0) / results.length,
    },
    category_breakdown: results.reduce((acc: CategoryBreakdown, r: TestResult) => {
      if (!acc[r.category]) {
        acc[r.category] = { count: 0, score: 0 };
      }
      acc[r.category].count++;
      // Handle both 0-1 and 0-100 score formats
      // If score is > 1, assume it's already a percentage, otherwise convert from 0-1 to 0-100
      const scoreValue = r.evaluation.score > 1 ? r.evaluation.score : r.evaluation.score * 100;
      acc[r.category].score += scoreValue;
      return acc;
    }, {} as CategoryBreakdown)
  };

  const isEthical = type === 'ethical';
  const isLogical = type === 'logical';
  const isTruthful = type === 'truthfulness';
  const mainScore = isEthical
    ? summary.ethical_alignment_score
    : isLogical
      ? summary.logical_correctness_score
      : summary.truthfulness_score;
  const successCount = isEthical
    ? summary.aligned_responses
    : isLogical
      ? summary.correct_responses
      : summary.truthful_responses;

  const getMetricData = () => {
    const metrics = summary.metrics;
    const keys = isEthical
      ? ['alignment', 'toxicity', 'reasoning']
      : isLogical
        ? ['correctness', 'reasoning', 'coherence']
        : ['factual_accuracy', 'honesty', 'transparency'];

    return keys.map((key) => ({
      name: key.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      value: Math.round(((metrics as any)[key] || 0) * 100),
    }));
  };

  const getCategoryData = () => {
    // Calculate average percentage for each category
    // data.score is the sum of (score * 100) for all items in the category
    // So we divide by count to get the average percentage
    const categoryData = Object.entries(summary.category_breakdown)
      .map(([category, data]) => {
        const averageScore = data.count > 0 ? data.score / data.count : 0;
        return {
          name: category,
          value: Math.round(averageScore), // Average percentage score for the category (0-100)
          count: data.count
        };
      })
      .filter(item => item.value >= 0 && item.value <= 100); // Ensure valid percentage range
    
    return categoryData;
  };

  const getStatusColor = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <ScrollArea className="h-[calc(100vh-8rem)] p-4">
      <div className="space-y-8">
        {/* Overall Score Card */}
        <Card className="p-6">
          <Title>
            Overall {isEthical ? 'Ethical Alignment' : isLogical ? 'Logical Reasoning' : 'Truthfulness'} Score
          </Title>
          <Metric className="mt-2">{Math.round(mainScore || 0)}%</Metric>
          <div className="mt-4">
            <Progress value={mainScore} className={getStatusColor(mainScore || 0)} />
          </div>
          <Text className="mt-2">
            {successCount} out of {summary.total_evaluated} responses {isEthical ? 'aligned' : isLogical ? 'correct' : 'truthful'}
          </Text>
        </Card>

        {/* Metrics Breakdown */}
        <Card className="p-6">
          <Title>Performance Metrics</Title>
          <BarList data={getMetricData()} className="mt-4" />
        </Card>

        {/* Category Performance */}
        <Card className="p-6">
          <Title>Category Performance</Title>
          <Text className="mt-2 text-sm text-gray-600">
            Average alignment score for each ethical category. Each segment represents one category's average performance.
          </Text>
          <div className="mt-4 relative">
            <DonutChart
              data={getCategoryData()}
              category="value"
              index="name"
              valueFormatter={(value) => `${value}%`}
              className="h-60"
              showAnimation={true}
              colors={["emerald", "blue", "amber", "rose", "indigo", "cyan"]}
            />
            {/* Overlay to hide confusing center total */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="bg-white dark:bg-gray-800 rounded-full w-32 h-32 flex items-center justify-center">
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    {Math.round(mainScore || 0)}%
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Overall Avg
                  </div>
                </div>
              </div>
            </div>
          </div>
          {/* Category Breakdown Table */}
          <div className="mt-6">
            <div className="space-y-2">
              {getCategoryData()
                .sort((a, b) => b.value - a.value)
                .map((item) => (
                  <div key={item.name} className="flex items-center justify-between p-2 rounded bg-gray-50">
                    <div className="flex items-center gap-2">
                      <Text className="font-medium">{item.name}</Text>
                      <Badge variant="secondary" className="text-xs">
                        {item.count} {item.count === 1 ? 'test' : 'tests'}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-32 bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${getStatusColor(item.value)}`}
                          style={{ width: `${Math.min(item.value, 100)}%` }}
                        />
                      </div>
                      <Text className="font-semibold w-12 text-right">{item.value}%</Text>
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </Card>

        {/* Detailed Results */}
        <Card className="p-6">
          <Title>Detailed Analysis</Title>
          <Tabs defaultValue="all" className="mt-4">
            <TabsList>
              <TabsTrigger value="all">All Results</TabsTrigger>
              <TabsTrigger value="success">
                {isEthical ? 'Aligned' : isLogical ? 'Correct' : 'Truthful'} ({successCount})
              </TabsTrigger>
              <TabsTrigger value="failure">
                Issues ({summary.total_evaluated - (successCount || 0)})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="all" className="mt-4">
              <div className="space-y-4">
                {results.map((result: TestResult) => (
                  <div
                    key={result.prompt_id}
                    className="border rounded-lg p-4 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <Badge variant={result.evaluation.score >= 0.7 ? "success" : "destructive"}>
                        {result.category}
                      </Badge>
                      <Text>{Math.round(result.evaluation.score * 100)}%</Text>
                    </div>
                    <div className="space-y-1">
                      <Text className="font-semibold">Question</Text>
                      <Text className="text-sm text-gray-800 bg-gray-50 rounded p-2 whitespace-pre-wrap">{result.prompt}</Text>
                    </div>
                    <div className="space-y-1">
                      <Text className="font-semibold">Response</Text>
                      <Text className="text-sm text-gray-900 bg-white rounded p-2 border whitespace-pre-wrap">{result.response}</Text>
                    </div>
                    <Text className="text-sm text-gray-500">
                      Expected: {result.expected_label}
                    </Text>
                    <Text className="text-sm">{result.evaluation.explanation}</Text>
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="success" className="mt-4">
              <div className="space-y-4">
                {results
                  .filter((r: TestResult) => r.evaluation.score >= 0.7)
                  .map((result: TestResult) => (
                    <div
                      key={result.prompt_id}
                      className="border rounded-lg p-4 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <Badge variant="success">{result.category}</Badge>
                        <Text>{Math.round(result.evaluation.score * 100)}%</Text>
                      </div>
                      <Text className="font-medium">{result.prompt}</Text>
                      <Text className="text-sm text-gray-500">
                        Expected: {result.expected_label}
                      </Text>
                      <Text className="text-sm">{result.evaluation.explanation}</Text>
                    </div>
                  ))}
              </div>
            </TabsContent>

            <TabsContent value="failure" className="mt-4">
              <div className="space-y-4">
                {results
                  .filter((r: TestResult) => r.evaluation.score < 0.7)
                  .map((result: TestResult) => (
                    <div
                      key={result.prompt_id}
                      className="border rounded-lg p-4 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <Badge variant="destructive">{result.category}</Badge>
                        <Text>{Math.round(result.evaluation.score * 100)}%</Text>
                      </div>
                      <Text className="font-medium">{result.prompt}</Text>
                      <Text className="text-sm text-gray-500">
                        Expected: {result.expected_label}
                      </Text>
                      <Text className="text-sm">{result.evaluation.explanation}</Text>
                    </div>
                  ))}
              </div>
            </TabsContent>
          </Tabs>
        </Card>
      </div>
    </ScrollArea>
  );
};
