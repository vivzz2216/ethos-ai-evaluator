import { useState } from 'react';
import { useToast } from '@/hooks/use-toast';

export interface TestResult {
  prompt_id: string;
  prompt: string;
  expected_label: string;
  category: string;
  evaluation: {
    score: number;
    aligned?: boolean;
    correct?: boolean;
    category: string;
    metrics: {
      alignment?: number;
      toxicity?: number;
      reasoning?: number;
      correctness?: number;
      coherence?: number;
    };
    explanation: string;
  };
}

export interface TestSummary {
  ethical_alignment_score?: number;
  logical_correctness_score?: number;
  truthfulness_score?: number;
  total_evaluated: number;
  aligned_responses?: number;
  correct_responses?: number;
  truthful_responses?: number;
  metrics: {
    alignment?: number;
    toxicity?: number;
    reasoning?: number;
    correctness?: number;
    coherence?: number;
    factual_accuracy?: number;
    honesty?: number;
    transparency?: number;
  };
  category_breakdown: {
    [key: string]: {
      count: number;
      score: number;
    };
  };
}

export interface TestResponse {
  results: TestResult[];
  summary: TestSummary;
}

export interface AutomatedTestResult {
  responses: string[];
  analysis: {
    [key: string]: any;
  };
}

export function useEthosTest() {
  const [isLoading, setIsLoading] = useState(false);
  const [ethicalResults, setEthicalResults] = useState<TestResponse | null>(null);
  const [logicalResults, setLogicalResults] = useState<TestResponse | null>(null);
  const [truthfulnessResults, setTruthfulnessResults] = useState<TestResponse | null>(null);
  const [automatedResults, setAutomatedResults] = useState<AutomatedTestResult | null>(null);
  const { toast } = useToast();

  const runEthicalTestDirect = async (maxSamples: number = 20, modelName?: string) => {
    setIsLoading(true);
    try {
      const requestBody: any = { max_samples: maxSamples };
      if (modelName) {
        requestBody.model_name = modelName;
      } else {
        requestBody.model_name = "sshleifer/tiny-gpt2";
      }
      
      const response = await fetch('http://localhost:8000/ethos/test/ethical', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to run ethical test: ${errorText}`);
      }

      const data = await response.json();
      setEthicalResults(data);
      return data;
    } catch (error) {
      console.error('Error running ethical test:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to run ethical alignment test',
        variant: 'destructive',
      });
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const runEthicalTest = async (modelResponses?: string[]) => {
    setIsLoading(true);
    try {
      // If no responses provided, send empty array or omit to trigger local model generation
      const requestBody: any = { max_samples: 20 };
      if (modelResponses && modelResponses.length > 0) {
        requestBody.responses = modelResponses;
      } else {
        // Omit responses to trigger automatic local model generation
        requestBody.model_name = "sshleifer/tiny-gpt2";
      }
      
      const response = await fetch('http://localhost:8000/ethos/test/ethical', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error('Failed to run ethical test');
      }

      const data = await response.json();
      setEthicalResults(data);
      return data;
    } catch (error) {
      console.error('Error running ethical test:', error);
      toast({
        title: 'Error',
        description: 'Failed to run ethical alignment test',
        variant: 'destructive',
      });
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const runLogicalTest = async (modelResponses: string[]) => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/ethos/test/logical', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ responses: modelResponses }),
      });

      if (!response.ok) {
        throw new Error('Failed to run logical test');
      }

      const data = await response.json();
      setLogicalResults(data);
      return data;
    } catch (error) {
      console.error('Error running logical test:', error);
      toast({
        title: 'Error',
        description: 'Failed to run logical reasoning test',
        variant: 'destructive',
      });
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const runTruthfulnessTest = async (modelResponses?: string[], modelName?: string) => {
    setIsLoading(true);
    try {
      const requestBody: any = { max_samples: 20 };
      if (modelResponses && modelResponses.length > 0) {
        requestBody.responses = modelResponses;
      } else if (modelName) {
        requestBody.model_name = modelName;
      } else {
        requestBody.model_name = "sshleifer/tiny-gpt2";
      }

      const response = await fetch('http://localhost:8000/ethos/test/truthfulness', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error('Failed to run truthfulness test');
      }

      const data = await response.json();
      setTruthfulnessResults(data);
      return data;
    } catch (error) {
      console.error('Error running truthfulness test:', error);
      toast({
        title: 'Error',
        description: 'Failed to run truthfulness test',
        variant: 'destructive',
      });
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const runTruthfulnessTestDirect = async (maxSamples: number = 20, modelName?: string) => {
    return runTruthfulnessTest(undefined, modelName);
  };

  const getPrompts = async (type: 'ethical' | 'logical' | 'truthfulness') => {
    try {
      const response = await fetch(`http://localhost:8000/ethos/prompts/${type}`);
      if (!response.ok) {
        throw new Error(`Failed to get ${type} prompts`);
      }
      return await response.json();
    } catch (error) {
      console.error(`Error getting ${type} prompts:`, error);
      toast({
        title: 'Error',
        description: `Failed to load ${type} test prompts`,
        variant: 'destructive',
      });
      return [];
    }
  };

  const runAutomatedTest = async (code: string) => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8000/ethos/test/automated', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ code, response_count: 3 }),
      });

      if (!response.ok) {
        throw new Error('Failed to run automated test');
      }

      const data = await response.json();
      setAutomatedResults(data);
      
      // Run ethical test with generated responses
      const ethical = await runEthicalTest(data.responses);
      
      // Also trigger full-run to generate artifacts (responses_log.json, ethics_scores.json, ethics_report.txt)
      try {
        await fetch('http://localhost:8000/ethos/test/ethical/full-run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            responses: data.responses,
            max_samples: 30,
            model_name: 'CodeAnalyzer-Auto',
            output_dir: 'data',
          }),
        });
      } catch (e) {
        console.warn('Failed to generate ethics artifacts:', e);
      }
      
      return data;
    } catch (error) {
      console.error('Error running automated test:', error);
      toast({
        title: 'Error',
        description: 'Failed to run automated code analysis',
        variant: 'destructive',
      });
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const clearResults = () => {
    setEthicalResults(null);
    setLogicalResults(null);
    setTruthfulnessResults(null);
    setAutomatedResults(null);
  };

  return {
    isLoading,
    ethicalResults,
    logicalResults,
    truthfulnessResults,
    automatedResults,
    runEthicalTest,
    runEthicalTestDirect,
    runLogicalTest,
    runTruthfulnessTest,
    runTruthfulnessTestDirect,
    runAutomatedTest,
    getPrompts,
    clearResults,
  };
}
