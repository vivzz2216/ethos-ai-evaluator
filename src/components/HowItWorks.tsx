import { Upload, Play, BarChart3, ArrowRight, Zap, Shield, TrendingUp } from "lucide-react";

const HowItWorks = () => {
  const steps = [
    {
      icon: Upload,
      title: "Import Model",
      description: "Connect your AI model through GitHub, API, or direct upload with enterprise-grade security",
      step: "01",
      color: "from-blue-500 to-cyan-500"
    },
    {
      icon: Play,
      title: "Run Prompts",
      description: "Execute comprehensive ethical, logical, and factual test scenarios with customizable parameters",
      step: "02",
      color: "from-purple-500 to-pink-500"
    },
    {
      icon: BarChart3,
      title: "Get Evaluation Report",
      description: "Receive detailed analysis with actionable insights and improvement recommendations",
      step: "03",
      color: "from-green-500 to-emerald-500"
    }
  ];

  const features = [
    {
      icon: Zap,
      title: "Lightning Fast",
      description: "Get results in seconds, not minutes"
    },
    {
      icon: Shield,
      title: "Enterprise Security",
      description: "SOC 2 compliant with end-to-end encryption"
    },
    {
      icon: TrendingUp,
      title: "Continuous Learning",
      description: "AI-powered insights that improve over time"
    }
  ];

  return (
    <section className="py-32 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-gradient-to-br from-background via-secondary/20 to-background"></div>
      
      <div className="max-w-7xl mx-auto relative z-10">
        <div className="text-center mb-20">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary mb-6">
            <span className="text-sm font-medium">Simple 3-Step Process</span>
          </div>
          <h2 className="text-5xl md:text-6xl font-bold mb-8 gradient-text neural-glow">
            How It Works
          </h2>
          <p className="text-xl md:text-2xl text-muted-foreground max-w-4xl mx-auto leading-relaxed">
            A streamlined, enterprise-grade process to evaluate your AI models across multiple dimensions
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-12 relative mb-20">
          {/* Enhanced Connection Lines */}
          <div className="hidden md:block absolute top-1/2 left-1/4 w-1/2 h-0.5 bg-gradient-to-r from-primary via-accent to-primary transform -translate-y-1/2 opacity-30"></div>

          {steps.map((step, index) => {
            const IconComponent = step.icon;
            return (
              <div key={index} className="relative group">
                {/* Glow Effect */}
                <div className={`absolute -inset-1 bg-gradient-to-r ${step.color} rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500`}></div>
                
                <div className="relative glass-card p-10 text-center group-hover:scale-105 transition-all duration-500 border border-border/20 hover:border-primary/30 hover-lift">
                  {/* Step Number */}
                  <div className={`absolute -top-6 -right-6 w-16 h-16 bg-gradient-to-r ${step.color} rounded-full flex items-center justify-center text-white font-bold text-xl shadow-lg group-hover:scale-110 transition-transform duration-300`}>
                    {step.step}
                  </div>

                  {/* Icon */}
                  <div className="mb-8 flex justify-center">
                    <div className={`w-24 h-24 bg-gradient-to-r ${step.color} rounded-2xl flex items-center justify-center neural-float shadow-lg group-hover:shadow-xl transition-shadow duration-300`}>
                      <IconComponent className="w-12 h-12 text-white" />
                    </div>
                  </div>

                  <h3 className="text-2xl font-bold mb-6 gradient-text">{step.title}</h3>
                  <p className="text-muted-foreground leading-relaxed text-lg">{step.description}</p>

                  {/* Arrow for mobile */}
                  {index < steps.length - 1 && (
                    <div className="md:hidden flex justify-center mt-8">
                      <div className="w-12 h-12 bg-gradient-to-r from-primary to-accent rounded-full flex items-center justify-center">
                        <ArrowRight className="w-6 h-6 text-white" />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-3 gap-8 mb-20">
          {features.map((feature, index) => {
            const IconComponent = feature.icon;
            return (
              <div key={index} className="group">
                <div className="glass-card p-8 text-center group-hover:scale-105 transition-all duration-500 border border-border/20 hover:border-accent/30">
                  <div className="mb-6 flex justify-center">
                    <div className="w-16 h-16 bg-gradient-to-r from-accent to-primary rounded-xl flex items-center justify-center neural-float">
                      <IconComponent className="w-8 h-8 text-primary-foreground" />
                    </div>
                  </div>
                  <h4 className="text-xl font-bold mb-4 gradient-text">{feature.title}</h4>
                  <p className="text-muted-foreground">{feature.description}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Enhanced Additional Info */}
        <div className="text-center">
          <div className="relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary to-accent rounded-3xl blur opacity-20 group-hover:opacity-40 transition duration-500"></div>
            <div className="relative glass-card p-12 max-w-5xl mx-auto border border-border/20 hover:border-primary/30">
              <h3 className="text-3xl font-bold mb-6 gradient-text">Real-time Analysis & Insights</h3>
              <p className="text-muted-foreground text-xl leading-relaxed mb-8">
                Our advanced platform provides instant, comprehensive feedback on your AI model's performance, 
                helping you identify areas for improvement and ensure responsible AI deployment with 
                enterprise-grade precision and reliability.
              </p>
              <div className="flex flex-wrap justify-center gap-6 text-sm text-muted-foreground">
                <span className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-primary rounded-full"></div>
                  <span>Real-time Processing</span>
                </span>
                <span className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-accent rounded-full"></div>
                  <span>Multi-dimensional Analysis</span>
                </span>
                <span className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-primary rounded-full"></div>
                  <span>Actionable Insights</span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;