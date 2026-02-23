import { Shield, Zap, BarChart3, Database, Globe, Lock, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

const HowItWorks = () => {
  const features = [
    {
      icon: Zap,
      title: "Rapid Development",
      description: "Building optimized testing infrastructure to deliver comprehensive AI evaluations efficiently.",
      metric: "In Progress",
      color: "text-blue-600"
    },
    {
      icon: Shield,
      title: "Security First",
      description: "Implementing enterprise-grade security measures and compliance standards for data protection.",
      metric: "Development",
      color: "text-green-600"
    },
    {
      icon: BarChart3,
      title: "Accuracy Focus",
      description: "Currently validating detection algorithms against benchmarks to ensure reliable results.",
      metric: "Beta Testing",
      color: "text-purple-600"
    }
  ];

  const capabilities = [
    {
      icon: Database,
      title: "Framework Support",
      description: "Building compatibility for major ML frameworks",
      details: ["PyTorch (Planned)", "TensorFlow (Planned)", "ONNX (In Dev)", "Hugging Face (Priority)", "OpenAI API (Ready)", "Custom Models (Future)"]
    },
    {
      icon: Globe,
      title: "Infrastructure Planning", 
      description: "Designing scalable deployment architecture",
      details: ["Local Testing", "Cloud Integration", "Regional Expansion", "Edge Computing (Roadmap)", "High Availability", "Auto-scaling (Future)"]
    },
    {
      icon: Lock,
      title: "Compliance Roadmap",
      description: "Planning regulatory compliance implementation",
      details: ["Privacy by Design", "Data Protection", "Security Standards", "Compliance Framework", "Audit Preparation", "Documentation"]
    }
  ];

  return (
    <section className="py-24 bg-gray-50 dark:bg-gray-800 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-20">
          <div className="mb-8">
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 dark:text-white mb-6 transition-colors duration-300">
              How ETHOS Works
            </h2>
            <p className="text-xl text-gray-600 dark:text-gray-300 max-w-4xl mx-auto mb-8 transition-colors duration-300">
              ETHOS evaluates your AI models across three critical dimensions to ensure they're safe, reliable, and trustworthy for production use.
            </p>
          </div>

          {/* Three Core Criteria */}
          <div className="grid md:grid-cols-3 gap-6 mb-16">
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 text-center transition-colors duration-300">
              <div className="w-12 h-12 bg-blue-50 dark:bg-blue-900/30 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Shield className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 transition-colors duration-300">Ethical Alignment</h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm transition-colors duration-300">Detects harmful content, bias, and ensures your AI follows ethical guidelines</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 text-center transition-colors duration-300">
              <div className="w-12 h-12 bg-purple-50 dark:bg-purple-900/30 rounded-xl flex items-center justify-center mx-auto mb-4">
                <BarChart3 className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 transition-colors duration-300">Logical Reasoning</h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm transition-colors duration-300">Tests if your AI can think logically and maintain coherent conversations</p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 text-center transition-colors duration-300">
              <div className="w-12 h-12 bg-green-50 dark:bg-green-900/30 rounded-xl flex items-center justify-center mx-auto mb-4">
                <Database className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2 transition-colors duration-300">Factual Accuracy</h3>
              <p className="text-gray-600 dark:text-gray-300 text-sm transition-colors duration-300">Catches when your AI makes up false information or "hallucinates"</p>
            </div>
          </div>
        </div>

        {/* Code Editor Demo */}
        <div className="mb-16">
          <h3 className="text-3xl font-bold text-gray-900 dark:text-white mb-8 text-center transition-colors duration-300">See ETHOS in Action</h3>
          
          <div className="bg-gray-900 rounded-2xl overflow-hidden shadow-2xl max-w-5xl mx-auto">
            {/* Code Editor Header */}
            <div className="bg-gray-800 px-6 py-4 flex items-center justify-between border-b border-gray-700">
              <div className="flex items-center space-x-4">
                <div className="flex space-x-2">
                  <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                  <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                </div>
                <span className="text-gray-300 text-sm font-medium">ethos_evaluation.py</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-green-400 text-xs">Running</span>
              </div>
            </div>
            
            {/* Code Content */}
            <div className="p-6 font-mono text-sm">
              <div className="text-gray-400 mb-2"># Testing AI model with ETHOS</div>
              <div className="text-blue-400 mb-1">import</div> <span className="text-white">ethos</span>
              <br/>
              <br/>
              <div className="text-gray-400 mb-2"># Initialize ETHOS evaluator</div>
              <div className="text-white">evaluator = ethos.Evaluator()</div>
              <br/>
              <div className="text-gray-400 mb-2"># Test for ethical alignment</div>
              <div className="text-white">result = evaluator.test_ethics(</div>
              <div className="ml-4 text-green-400">"Should I share personal data without consent?"</div>
              <div className="text-white">)</div>
              <br/>
              <div className="text-yellow-400">print</div><span className="text-white">(result.score)  </span><span className="text-gray-400"># 0.95 - Safe</span>
              <br/>
              <br/>
              <div className="text-gray-400 mb-2"># Test for logical reasoning</div>
              <div className="text-white">logic_test = evaluator.test_logic(</div>
              <div className="ml-4 text-green-400">"If all cats are animals, and Fluffy is a cat..."</div>
              <div className="text-white">)</div>
              <br/>
              <div className="text-yellow-400">print</div><span className="text-white">(logic_test.coherence)  </span><span className="text-gray-400"># 0.98 - Excellent</span>
              <br/>
              <br/>
              <div className="text-gray-400 mb-2"># Check for hallucinations</div>
              <div className="text-white">fact_check = evaluator.verify_facts(</div>
              <div className="ml-4 text-green-400">"The moon landing happened in 1969"</div>
              <div className="text-white">)</div>
              <br/>
              <div className="text-yellow-400">print</div><span className="text-white">(fact_check.accuracy)  </span><span className="text-gray-400"># 1.0 - Verified</span>
            </div>
            
            {/* Output Terminal */}
            <div className="bg-black px-6 py-4 border-t border-gray-700">
              <div className="text-green-400 text-xs mb-2">✓ Ethics Test: PASSED (Score: 0.95)</div>
              <div className="text-green-400 text-xs mb-2">✓ Logic Test: PASSED (Coherence: 0.98)</div>
              <div className="text-green-400 text-xs mb-2">✓ Fact Check: PASSED (Accuracy: 1.0)</div>
              <div className="text-blue-400 text-xs">🎉 Your AI model is ready for production!</div>
            </div>
          </div>
        </div>

        

        {/* Key Performance Metrics */}
        <div className="grid md:grid-cols-3 gap-8 mb-20">
          {features.map((feature, index) => {
            const IconComponent = feature.icon;
            return (
              <div key={index} className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md dark:hover:shadow-xl transition-all duration-300">
                <div className={`w-12 h-12 bg-gray-50 dark:bg-gray-700 rounded-xl flex items-center justify-center mb-6`}>
                  <IconComponent className={`w-6 h-6 ${feature.color}`} />
                </div>
                <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2 transition-colors duration-300">{feature.metric}</div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3 transition-colors duration-300">{feature.title}</h3>
                <p className="text-gray-600 dark:text-gray-300 leading-relaxed transition-colors duration-300">{feature.description}</p>
              </div>
            );
          })}
        </div>



        {/* Capabilities Grid */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          {capabilities.map((capability, index) => {
            const IconComponent = capability.icon;
            return (
              <div key={index} className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-sm border border-gray-200 dark:border-gray-700 transition-colors duration-300">
                <div className="w-12 h-12 bg-blue-50 dark:bg-blue-900/30 rounded-xl flex items-center justify-center mb-6">
                  <IconComponent className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3 transition-colors duration-300">{capability.title}</h3>
                <p className="text-gray-600 dark:text-gray-300 mb-4 transition-colors duration-300">{capability.description}</p>
                <div className="space-y-2">
                  {capability.details.map((detail, idx) => (
                    <div key={idx} className="flex items-center text-sm text-gray-600 dark:text-gray-300 transition-colors duration-300">
                      <div className="w-1.5 h-1.5 bg-blue-600 dark:bg-blue-400 rounded-full mr-3"></div>
                      {detail}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* CTA Section */}
        <div className="bg-gradient-to-br from-blue-50 to-purple-50 dark:from-gray-800 dark:to-gray-700 rounded-2xl p-12 border border-blue-200 dark:border-gray-600 text-center transition-colors duration-300">
          <h3 className="text-3xl font-bold text-gray-900 dark:text-white mb-4 transition-colors duration-300">
            Ready to deploy reliable AI?
          </h3>
          <p className="text-gray-600 dark:text-gray-300 mb-8 max-w-2xl mx-auto text-lg transition-colors duration-300">
            Be among the first to experience ETHOS as we build the future of AI model validation and testing.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-4 text-lg shadow-lg hover:shadow-xl transition-all duration-300">
              Start Free Trial
              <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
            <Button variant="outline" size="lg" className="px-8 py-4 text-lg border-2 border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 text-gray-700 dark:text-white hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white/50 dark:hover:bg-gray-800/50 transition-all duration-300">
              Schedule Demo
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;