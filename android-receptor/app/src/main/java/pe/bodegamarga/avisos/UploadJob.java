package pe.bodegamarga.avisos;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

public final class UploadJob extends JobService {
    private final ConcurrentHashMap<Integer,AtomicBoolean> stopping=new ConcurrentHashMap<>();
    static void schedule(Context c){
        if(!Config.enabled(c))return;
        JobScheduler jobs=(JobScheduler)c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if(jobs.getPendingJob(901)==null)jobs.schedule(new JobInfo.Builder(901,new ComponentName(c,UploadJob.class))
          .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true).setPeriodic(15*60*1000L).build());
    }
    static void retry(Context c){
        if(!Config.enabled(c))return;
        JobScheduler jobs=(JobScheduler)c.getSystemService(Context.JOB_SCHEDULER_SERVICE);
        if(jobs.getPendingJob(902)==null)jobs.schedule(new JobInfo.Builder(902,new ComponentName(c,UploadJob.class))
          .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPersisted(true)
          .setBackoffCriteria(10000,JobInfo.BACKOFF_POLICY_EXPONENTIAL).build());
    }
    static void cancel(Context c){JobScheduler jobs=(JobScheduler)c.getSystemService(Context.JOB_SCHEDULER_SERVICE);jobs.cancel(901);jobs.cancel(902);}
    @Override public boolean onStartJob(JobParameters params){
        AtomicBoolean stop=new AtomicBoolean(false);stopping.put(params.getJobId(),stop);
        Uploader.EXEC.execute(()->{
            boolean retry=Uploader.drain(getApplicationContext(),true,()->!stop.get());
            stopping.remove(params.getJobId(),stop);if(!stop.get())jobFinished(params,retry);
        });return true;
    }
    @Override public boolean onStopJob(JobParameters params){
        AtomicBoolean stop=stopping.remove(params.getJobId());if(stop!=null)stop.set(true);return Config.enabled(this);
    }
}
