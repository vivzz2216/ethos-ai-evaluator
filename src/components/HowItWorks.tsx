import { Upload, Play, BarChart3, ArrowRight } from "lucide-react";

const HowItWorks = () => {
  const steps = [
    {
      icon: Upload,
      title: "Import Model",
      description: "Connect your AI model through GitHub, API, or direct upload",
      step: "01"
    },
    {
      icon: Play,
      title: "Run Prompts",
      description: "Execute ethical, logical, and factual test scenarios",
      step: "02"
    },
    {
      icon: BarChart3,
      title: "Get Evaluation Report",
      description: "Receive comprehensive analysis and improvement recommendations",
      step: "03"
    }
  ];

  return (
    <section className="py-24 px-4 sm:px-6 lg:px-8 bg-secondary/30">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold mb-6 gradient-text neural-glow">
            How It Works
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            A streamlined process to evaluate your AI models across multiple dimensions
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 relative">
          {/* Connection Lines */}
          <div className="hidden md:block absolute top-1/2 left-1/3 w-1/3 h-0.5 bg-gradient-to-r from-primary to-accent transform -translate-y-1/2"></div>
          <div className="hidden md:block absolute top-1/2 right-1/3 w-1/3 h-0.5 bg-gradient-to-r from-primary to-accent transform -translate-y-1/2"></div>

          {steps.map((step, index) => {
            const IconComponent = step.icon;
            return (
              <div key={index} className="relative">
                <div className="glass-card p-8 text-center group hover:scale-105 transition-all duration-500 relative">
                  {/* Step Number */}
                  <div className="absolute -top-4 -right-4 w-12 h-12 bg-primary rounded-full flex items-center justify-center text-primary-foreground font-bold text-lg animate-pulse-glow">
                    {step.step}
                  </div>

                  {/* Icon */}
                  <div className="mb-6 flex justify-center">
                    <div className="w-20 h-20 bg-primary/20 rounded-full flex items-center justify-center neural-float">
                      <IconComponent className="w-10 h-10 text-primary" />
                    </div>
                  </div>

                  <h3 className="text-2xl font-bold mb-4 gradient-text">{step.title}</h3>
                  <p className="text-muted-foreground leading-relaxed">{step.description}</p>

                  {/* Arrow for mobile */}
                  {index < steps.length - 1 && (
                    <div className="md:hidden flex justify-center mt-6">
                      <ArrowRight className="w-6 h-6 text-primary" />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Additional Info */}
        <div className="mt-16 text-center">
          <div className="glass-card p-8 max-w-4xl mx-auto">
            <h3 className="text-2xl font-bold mb-4 gradient-text">Real-time Analysis</h3>
            <p className="text-muted-foreground text-lg leading-relaxed">
              Our platform provides instant feedback on your AI model's performance, 
              helping you identify areas for improvement and ensure responsible AI deployment.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};

export default HowItWorks;