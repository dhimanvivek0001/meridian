# LinkedIn post (draft)

I spent the last few weeks treating 31 million H&M transactions like a real company's data.

I named the company "Meridian" and worked it end to end, the way an analytics team would. These are the five things that surprised me:

1. The sales drop wasn't COVID. Sales were already down 11% before lockdown. Most of it came from tops and trousers, and T-shirts fell 31% mainly because 20% fewer designs were on sale. That's a buying decision, not a pandemic.

2. The regression got the sign wrong. It said cutting prices lowers sales, because shops discount items that are already struggling. Only a randomised test found the real effect.

3. The marketing model over-promised 26x. Budget optimizers push money to wherever the model is most wrong. Test, then move.

4. Simple beat clever. A seasonal "same week last year" forecast tied machine learning. In the recommender, simple rules did most of the work.

5. The biggest money was in stopping bad decisions. All the models together were worth about €3.7m a year. A blanket 50%-off sale would lose €9.8m.

I also caught my own mistake: I'd valued saved customers on revenue, not margin. Fixing it cut one estimate from €10m to €2.75m. I kept the correction in the write-up.

The churn model now runs as a weekly Databricks job with data checks, drift monitoring and a registered model.

Code, findings and a CEO one-pager: [GitHub link]

I'm looking for Data / Business / Marketing Analyst roles in Ireland. Happy to talk through any of it.

#DataAnalytics #DataScience #Databricks #MachineLearning #Galway
