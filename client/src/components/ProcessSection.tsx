import { Upload, Play, FileText } from "lucide-react";

const ProcessSection = () => {
  const steps = [
    {
      title: "Upload Your Model",
      description: "Connect your AI model via API or upload your model files directly to our platform.",
      icon: Upload
    },
    {
      title: "Run Tests",
      description: "Our system automatically tests your AI for ethics, logic, and accuracy across hundreds of scenarios.",
      icon: Play
    },
    {
      title: "Get Results", 
      description: "Receive detailed reports showing exactly where your AI excels and where it needs improvement.",
      icon: FileText
    }
  ];

  return (
    <section className="py-24 bg-white dark:bg-black relative overflow-hidden">
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        {/* Header */}
        <div className="text-center mb-20">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 dark:text-white mb-6">
            Simple 3-Step Process
          </h2>
          <p className="text-xl text-gray-700 dark:text-gray-300 max-w-3xl mx-auto">
            Get your AI model evaluated and production-ready in three simple steps
          </p>
        </div>

        {/* Steps Grid */}
        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((step, index) => {
            const IconComponent = step.icon;
            return (
              <div key={index} className="text-center">
                {/* Icon */}
                <div className="w-16 h-16 bg-blue-600/90 dark:bg-blue-600/80 backdrop-blur-lg rounded-2xl flex items-center justify-center mx-auto mb-6 border border-blue-500/30 dark:border-blue-400/30 shadow-2xl">
                  <IconComponent className="w-8 h-8 text-white" />
                </div>

                {/* Content */}
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  {step.title}
                </h3>
                <p className="text-gray-700 dark:text-gray-300 text-lg leading-relaxed">
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>

        
      </div>
    </section>
  );
};

export default ProcessSection;